# C11 互动座驾素材

- `black-00.webp` 至 `black-35.webp`：从恢复后的 dcd3d-mirror 金属黑缓存逐字节复制的 36 帧 RGBA 图片，未重编码。
- `frames.json`：原图尺寸、顺序、原文件 SHA-256、逐帧牌照四边形。
- `plate.svg`：独立的浅绿渐变、黑字专属牌面「沪B·AY7772」。
- `showroom.png`：独立暖灰展厅背景，通过内置 imagegen 生成。车辆不在背景文件里。

`vehicle-viewer.js` 在透明 canvas 上绘制原图，再用透视网格绘制牌面。
牌面合成使用 `source-atop`，因此车辆、玻璃、地面阴影的原始 alpha 不变；
背景由 CSS 单独显示。没有回源代理、第三方页面、埋点或 8788 服务依赖。

重建原图与牌照坐标：`python3 scripts/import_vehicle_frames.py /path/to/dcd3d-mirror/mirror`。
准备脚本依赖 Pillow / numpy，仅在本机生成素材时使用，应用运行时不需要 numpy。
修改牌号只需改 `plate.svg` 的字形，保持 `frames.json` 的 `plateText` 同步。

背景生成提示词：

> EMPTY premium minimalist automotive showroom, warm light-gray / off-white
> seamless walls, subtle vertical panels and shallow recess on far right,
> broad diffuse daylight from upper left, matte pale warm-gray concrete floor
> in lower 40%, eye-level neutral automotive photography, central empty space
> for a separately composited black SUV. No cars, people, furniture, plants,
> text, logos, watermarks, harsh sun patches or glossy reflections.
