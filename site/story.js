function initialize() {
  const root = document.documentElement;
  const italian = root.lang === "it";
  const languageLinks = document.querySelectorAll(".language-switch a");
  function updateLanguageLinks() {
    languageLinks.forEach(link => {
      const target = new URL(link.href);
      target.searchParams.set("scoutTheme", root.dataset.theme);
      target.hash = location.hash;
      link.href = target.href;
    });
  }
  updateLanguageLinks();
  addEventListener("hashchange", updateLanguageLinks);
  const themeButton = document.querySelector("#theme-toggle");
  function labelTheme() {
    themeButton.textContent = root.dataset.theme === "dark"
      ? (italian ? "Tema chiaro" : "Light edition")
      : (italian ? "Tema scuro" : "Dark edition");
  }
  labelTheme();
  themeButton.hidden = false;
  themeButton.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    labelTheme();
    updateLanguageLinks();
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

try {
  initialize();
} catch (error) {
  document.querySelector("#enhancement-error").hidden = false;
  console.error("Report viewing controls failed:", error);
}
