/* Original RGBA frames stay untouched. Only the plate plane is composited. */
(() => {
  "use strict";
  const root = document.getElementById("vehicleViewer");
  if (!root || document.body.classList.contains("upload-page")) return;
  const canvas = root.querySelector("canvas");
  const poster = root.querySelector(".vehicle-poster");
  const hint = document.getElementById("vehicleHint");
  const previous = root.querySelector("[data-vehicle-prev]");
  const next = root.querySelector("[data-vehicle-next]");
  const context = canvas.getContext("2d");
  if (!context) return;
  const version = document.querySelector('meta[name="build"]').content;
  const asset = name => `/vehicle/${name}?v=${encodeURIComponent(version)}`;
  let manifest, plate, current = 0, desired = 0, drag = null, requested = 0;
  let hasInteracted = false;
  const frames = new Map();
  const loading = new Map();
  const failed = new Set();

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = src;
    });
  }

  function loadFrame(index) {
    if (frames.has(index)) return Promise.resolve(frames.get(index));
    if (loading.has(index)) return loading.get(index);
    const promise = loadImage(asset(manifest.frames[index].src)).then(image => {
      frames.set(index, image);
      failed.delete(index);
      return image;
    }).catch(error => {
      failed.add(index);
      throw error;
    }).finally(() => loading.delete(index));
    loading.set(index, promise);
    return promise;
  }

  // Unit square -> the frame's measured perspective quadrilateral.
  function projector(q) {
    const [[x0,y0],[x1,y1],[x2,y2],[x3,y3]] = q;
    const dx1=x1-x2, dx2=x3-x2, dy1=y1-y2, dy2=y3-y2;
    const sx=x0-x1+x2-x3, sy=y0-y1+y2-y3;
    const det=dx1*dy2-dx2*dy1;
    const g=det ? (sx*dy2-dx2*sy)/det : 0;
    const h=det ? (dx1*sy-sx*dy1)/det : 0;
    return (u,v) => {
      const w=g*u+h*v+1;
      return [((x1-x0+g*x1)*u+(x3-x0+h*x3)*v+x0)/w,
              ((y1-y0+g*y1)*u+(y3-y0+h*y3)*v+y0)/w];
    };
  }

  function triangle(source, destination) {
    const [[sx0,sy0],[sx1,sy1],[sx2,sy2]]=source;
    const [[x0,y0],[x1,y1],[x2,y2]]=destination;
    const det=(sx1-sx0)*(sy2-sy0)-(sx2-sx0)*(sy1-sy0);
    if (Math.abs(det)<0.001) return;
    const a=((x1-x0)*(sy2-sy0)-(x2-x0)*(sy1-sy0))/det;
    const b=((y1-y0)*(sy2-sy0)-(y2-y0)*(sy1-sy0))/det;
    const c=((x2-x0)*(sx1-sx0)-(x1-x0)*(sx2-sx0))/det;
    const d=((y2-y0)*(sx1-sx0)-(y1-y0)*(sx2-sx0))/det;
    context.save();
    context.beginPath();
    context.moveTo(x0,y0); context.lineTo(x1,y1); context.lineTo(x2,y2); context.closePath();
    context.clip();
    context.transform(a,b,c,d,x0-a*sx0-c*sy0,y0-b*sx0-d*sy0);
    context.drawImage(plate,0,0);
    context.restore();
  }

  function draw(index) {
    context.clearRect(0,0,canvas.width,canvas.height);
    context.drawImage(frames.get(index),0,0);
    const q=manifest.frames[index].plate;
    if (q) {
      context.save();
      context.globalCompositeOperation="source-atop";
      context.beginPath();
      q.forEach(([x,y],i) => i ? context.lineTo(x,y) : context.moveTo(x,y));
      context.closePath();context.fillStyle="#a5dfb1";context.fill();
      const project=projector(q), columns=8;
      // A small perspective mesh keeps the SVG's lettering natural at oblique angles.
      for (let x=0; x<columns; x++) {
        const u=x/columns, v=(x+1)/columns;
        triangle([[u*plate.width,0],[v*plate.width,0],[v*plate.width,plate.height]],
                 [project(u,0),project(v,0),project(v,1)]);
        triangle([[u*plate.width,0],[v*plate.width,plate.height],[u*plate.width,plate.height]],
                 [project(u,0),project(v,1),project(u,1)]);
      }
      context.restore();
    }
    current=index;
    root.dataset.frame=String(index);
    root.setAttribute("aria-valuenow",String(index));
    root.setAttribute("aria-valuetext",`车辆角度 ${index*10} 度`);
  }

  function show(index) {
    if (!manifest || !plate) return;
    desired=((index%manifest.frames.length)+manifest.frames.length)%manifest.frames.length;
    const target=desired;
    hasInteracted=true;
    hint.textContent="左右拖动 · 360° 查看";
    if (frames.has(target)) {
      if (!requested) requested=requestAnimationFrame(() => {
        requested=0;if (frames.has(desired)) draw(desired);
      });
    } else {
      loadFrame(target).then(() => {
        if (desired===target) draw(target);
      }).catch(() => { if (desired===target) hint.textContent="此角度暂未加载，可继续拖动重试"; });
    }
  }

  function step(delta) { show(desired+delta); }
  previous.addEventListener("click",() => step(-1));
  next.addEventListener("click",() => step(1));
  root.addEventListener("keydown",event => {
    const actions={ArrowLeft:()=>step(-1),ArrowRight:()=>step(1),Home:()=>show(0),End:()=>show(manifest.frames.length-1)};
    if (manifest && actions[event.key] && event.target===root) {event.preventDefault();actions[event.key]();}
  });
  root.addEventListener("pointerdown",event => {
    if (root.dataset.ready!=="true" || event.button!==0 || event.target.closest("button")) return;
    drag={id:event.pointerId,x:event.clientX,y:event.clientY,frame:desired,axis:null};
    root.setPointerCapture(event.pointerId);
  });
  root.addEventListener("pointermove",event => {
    if (!drag || event.pointerId!==drag.id) return;
    const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
    if (!drag.axis && Math.max(Math.abs(dx),Math.abs(dy))>6) drag.axis=Math.abs(dx)>Math.abs(dy)?"x":"y";
    if (drag.axis!=="x") return;
    root.classList.add("is-dragging");
    const pixelsPerFrame=Math.max(7,root.clientWidth/36);
    show(drag.frame-Math.round(dx/pixelsPerFrame));
  });
  for (const name of ["pointerup","pointercancel","lostpointercapture"]) root.addEventListener(name,() => {
    drag=null;root.classList.remove("is-dragging");
  });

  async function init() {
    try {
      const response=await fetch(asset("frames.json"));
      if (!response.ok) throw new Error("Vehicle manifest unavailable");
      manifest=await response.json();
      canvas.width=manifest.width;canvas.height=manifest.height;
      current=desired=manifest.initialFrame;
      [plate]=await Promise.all([loadImage(asset("plate.svg")),loadFrame(current)]);
      draw(current);
      poster.hidden=true;canvas.hidden=false;
      root.dataset.ready="true";
      root.setAttribute("tabindex","0");
      root.setAttribute("role","slider");
      root.setAttribute("aria-valuemin","0");
      root.setAttribute("aria-valuemax",String(manifest.frames.length-1));
      previous.hidden=next.hidden=false;
      // Four workers limit bandwidth pressure on the rest of the dashboard.
      let cursor=1;
      await Promise.all(Array.from({length:4},async () => {
        while (cursor<manifest.frames.length) {
          const index=cursor++;
          await loadFrame(index).catch(() => {});
        }
      }));
      root.dataset.loaded=String(frames.size);
      if (failed.size && !hasInteracted) hint.textContent="部分角度未加载，拖动时可重试";
    } catch (_) {
      // Keep the original static banner when the viewer cannot start.
      manifest=null;
      hint.textContent="座驾静态展示";
      root.dataset.ready="false";
    }
  }
  // The standalone upload screen shares this HTML but never downloads the sprites.
  if ("IntersectionObserver" in window) {
    const observer=new IntersectionObserver(entries => {
      if (entries.some(entry=>entry.isIntersecting)) {observer.disconnect();init();}
    },{rootMargin:"120px"});
    observer.observe(root);
  } else init();
})();
