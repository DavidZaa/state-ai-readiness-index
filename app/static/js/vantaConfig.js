// Carried over from BrainBow, with two changes.
//
// The globe is initialised from the CSS custom properties rather than
// hardcoded hex values, so the theme switcher only has to change the
// stylesheet and the background follows. And it respects reduced-motion: a
// slowly rotating globe behind a data table is exactly the kind of ambient
// animation people turn that setting off for.

let vantaEffect = null;

function cssColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value ? Number.parseInt(value.replace("#", "0x"), 16) : fallback;
}

function prefersStillness() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function initVanta() {
  if (typeof VANTA === "undefined" || prefersStillness()) return;

  if (vantaEffect) vantaEffect.destroy();

  vantaEffect = VANTA.GLOBE({
    el: ".vanta-globe",
    mouseControls: true,
    touchControls: true,
    gyroControls: false,
    minHeight: 200.0,
    minWidth: 200.0,
    scale: 1.0,
    scaleMobile: 1.0,
    color: cssColor("--text", 0xeeeeee),
    color2: cssColor("--accent", 0xff00ee),
    backgroundColor: cssColor("--bg", 0x24242c),
  });
}

const THEMES = {
  dark: { "--box": "#373a40", "--text": "#eeeeee", "--bg": "#24242c", "--muted": "#686d76" },
  light: { "--box": "#e6e6e2", "--text": "#24242c", "--bg": "#f4f4f0", "--muted": "#5b5f66" },
};

function applyTheme(theme) {
  const root = document.documentElement;
  const tokens = THEMES[theme] || THEMES.dark;

  Object.entries(tokens).forEach(([token, value]) => root.style.setProperty(token, value));

  try {
    localStorage.setItem("sari-theme", theme);
  } catch {
    // Site data blocked. The theme still applies for this page view.
  }

  initVanta();
}

function storedTheme() {
  try {
    return localStorage.getItem("sari-theme") || "dark";
  } catch {
    return "dark";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(storedTheme());

  const toggle = document.querySelector("[data-theme-toggle]");

  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = storedTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      toggle.textContent = next === "dark" ? "Light" : "Dark";
    });
  }
});
