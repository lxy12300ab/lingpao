// Set appearance before CSS loads to avoid a light flash on iPhone.
(() => {
  const media = matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try {
    preference = localStorage.getItem("leapAppearance") || "system";
  } catch (_) {}
  if (!["system", "light", "dark"].includes(preference)) preference = "system";
  function apply() {
    const theme =
      preference === "system" ? (media.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.appearance = preference;
    document.querySelector("#themeColor").content =
      theme === "dark" ? "#111412" : "#f5f5f2";
    window.dispatchEvent(new CustomEvent("appearancechange"));
  }
  window.LeapTheme = {
    get: () => preference,
    set(value) {
      if (!["system", "light", "dark"].includes(value)) return;
      preference = value;
      try {
        localStorage.setItem("leapAppearance", value);
      } catch (_) {}
      apply();
    },
  };
  media.addEventListener("change", apply);
  apply();
})();
