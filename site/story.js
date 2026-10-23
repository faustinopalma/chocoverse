function initialize() {
  const root = document.documentElement;
  const themeButton = document.querySelector("#theme-toggle");
  function labelTheme() {
    themeButton.textContent = root.dataset.theme === "dark" ? "Light edition" : "Dark edition";
  }
  labelTheme();
  themeButton.hidden = false;
  themeButton.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    labelTheme();
  });

  const dialog = document.querySelector("#evidence-dialog");
  document.querySelectorAll("[data-zoom]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || typeof dialog.showModal !== "function") return;
      event.preventDefault();
      const original = link.querySelector("img");
      const image = document.querySelector("#enlarged-evidence");
      image.src = original.src;
      image.alt = original.alt;
      document.querySelector("#evidence-caption").textContent = original.alt;
      dialog.querySelector(".chart-legend")?.remove();
      const legend = link.closest("figure").querySelector(".chart-legend");
      if (legend) document.querySelector("#evidence-caption").after(legend.cloneNode(true));
      document.querySelector("#original-evidence").href = original.src;
      dialog.showModal();
    });
  });
  document.querySelector("#close-evidence").addEventListener("click", () => dialog.close());
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      dialog.close();
    }
  });
}

async function initializeWorld() {
  const viewer = document.querySelector("#chocoverse-model");
  const status = document.querySelector("#world-status");
  const reset = document.querySelector("#world-reset");
  const fail = (error) => {
    status.textContent = "3D could not load. Check WebGL support, or use Download 3D model.";
    viewer.querySelector(".world-loading").textContent = "The 3D view is unavailable.";
    reset.hidden = true;
    console.error("Chocoverse 3D failed:", error);
  };
  viewer.addEventListener("error", fail);
  viewer.addEventListener("load", () => {
    status.textContent = "Interactive 3D · Drag to orbit. Scroll or pinch to zoom.";
    reset.hidden = false;
  });
  reset.addEventListener("click", () => {
    viewer.cameraOrbit = "32deg 58deg auto";
    viewer.cameraTarget = "auto auto auto";
    viewer.fieldOfView = "32deg";
    viewer.resetTurntableRotation();
  });
  const start = async () => {
    status.textContent = "Loading Chocoverse in 3D…";
    try {
      await import("./vendor/model-viewer.min.js");
      viewer.src = "assets/chocoverse.glb";
    } catch (error) {
      fail(error);
    }
  };
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some(entry => entry.isIntersecting)) {
        observer.disconnect();
        void start();
      }
    }, { rootMargin: "200px" });
    observer.observe(viewer);
  } else {
    await start();
  }
}

try {
  initialize();
  void initializeWorld();
} catch (error) {
  document.querySelector("#enhancement-error").hidden = false;
  console.error("Report viewing controls failed:", error);
}
