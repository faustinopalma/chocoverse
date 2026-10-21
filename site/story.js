import { coverDays, supportedGrain, assessClaim } from "./learning.js";

function initialize() {
  const root = document.documentElement;
  const daily = JSON.parse(document.querySelector("#daily-data").textContent);
  if (daily.length !== 31 || daily.some((item, i) => item.day !== i + 1 || !Number.isFinite(item.kg))) {
    throw new Error("The daily evidence is incomplete.");
  }
  const themeButton = document.querySelector("#theme-toggle");
  themeButton.hidden = false;
  themeButton.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    themeButton.setAttribute("aria-label", `Switch to ${root.dataset.theme === "dark" ? "light" : "dark"} theme`);
  });

  document.querySelectorAll("[data-comparison] button").forEach((button) => {
    button.addEventListener("click", () => {
      const correct = button.dataset.answer === "fair";
      document.querySelector("#comparison-feedback").textContent = correct
        ? "Exactly. Change the channel filter only: 82 ÷ 1,994 × 100 = 4.11%."
        : "That changes the product and territory too. We have no comparable denominator for that choice.";
      document.querySelector(".share-result").hidden = !correct;
      document.querySelectorAll("[data-comparison] button").forEach((choice) => {
        choice.classList.toggle("chosen", choice === button);
      });
    });
  });

  function updatePolicy() {
    const selected = [...document.querySelectorAll(".policy-options input:checked")].map((input) => Number(input.value));
    const result = coverDays(selected);
    document.querySelector("#cover-value").textContent = `${result} days`;
    const rule = selected.length === 1 ? "One selected value is used directly." : "No unique selection: use the three-day default.";
    document.querySelector("#cover-reason").textContent = `${rule} ${result === 3
      ? "The observed three-day target is 1,252.7 kg."
      : "A target for this selection has not been evaluated here."}`;
  }
  document.querySelectorAll(".policy-options input").forEach((input) => input.addEventListener("change", updatePolicy));
  updatePolicy();

  const slider = document.querySelector("#day-slider");
  function updateDay() {
    const item = daily[Number(slider.value) - 1];
    document.querySelector("#day-value").textContent = `${item.day} August · ${item.kg} kg`;
    slider.setAttribute("aria-valuetext", `${item.day} August 2034, ${item.kg} kilograms`);
    document.querySelectorAll(".day-cell").forEach((cell) => {
      cell.classList.toggle("selected-day", Number(cell.dataset.day) === item.day);
    });
  }
  slider.addEventListener("input", updateDay);
  document.querySelector("#full-month").addEventListener("change", (event) => {
    const complete = event.target.checked;
    document.querySelectorAll(".day-cell").forEach((cell) => {
      cell.classList.toggle("omitted-day", !complete && Number(cell.dataset.day) > 25);
    });
    slider.max = complete ? "31" : "25";
    if (!complete && Number(slider.value) > 25) slider.value = "25";
    document.querySelector("#coverage-status").textContent = complete
      ? "31 of 31 days included. The month is complete."
      : "25 of 31 days included. August 26–31 are missing: the monthly view is incomplete.";
    updateDay();
  });
  updateDay();

  function updateGrain() {
    const scope = document.querySelector("#grain-select").value;
    const support = supportedGrain(scope);
    const labels = { sales: "Sell-out", production: "Released production", cash: "Closing cash" };
    const container = document.querySelector("#grain-result");
    container.replaceChildren();
    for (const [metric, allowed] of Object.entries(support)) {
      const card = document.createElement("div");
      card.className = `grain-card ${allowed ? "supported" : "unavailable"}`;
      const name = document.createElement("strong");
      name.textContent = labels[metric];
      const status = document.createElement("span");
      status.textContent = allowed ? "Supported" : "Unavailable at this grain";
      card.append(name, status);
      container.append(card);
    }
  }
  document.querySelector("#grain-select").addEventListener("change", updateGrain);
  updateGrain();

  document.querySelectorAll("[data-claim]").forEach((button) => {
    button.addEventListener("click", () => {
      const result = assessClaim(button.dataset.claim);
      document.querySelector("#quiz-feedback").textContent = result.message;
      document.querySelectorAll("[data-claim]").forEach((choice) => choice.classList.toggle("chosen", choice === button));
      document.querySelector(".briefing-stamp").hidden = !result.correct;
      document.querySelector("#chapter-8").classList.toggle("quiz-complete", result.correct);
    });
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
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
        dialog.close();
      }
    }
  });

  const sections = [...document.querySelectorAll(".chapter")];
  let scheduled = false;
  function updateProgress() {
    const threshold = Math.min(window.innerHeight * 0.4, 280);
    let current = 0;
    for (const section of sections) {
      if (section.getBoundingClientRect().top <= threshold) current = Number(section.dataset.step);
    }
    document.querySelector("#reading-progress").value = current;
    document.querySelector("#reading-label").textContent = current ? `Chapter ${current} / 8` : "Eight chapters. One decision.";
    document.querySelectorAll("[data-nav]").forEach((link) => {
      if (Number(link.dataset.nav) === current) link.setAttribute("aria-current", "step");
      else link.removeAttribute("aria-current");
    });
    scheduled = false;
  }
  window.addEventListener("scroll", () => {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(updateProgress);
    }
  }, { passive: true });
  window.addEventListener("resize", updateProgress);
  updateProgress();
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("arrived");
          observer.unobserve(entry.target);
        }
      }
    }, { threshold: 0.1 });
    document.querySelectorAll("[data-reveal]").forEach((element) => observer.observe(element));
  }
  root.classList.add("enhanced");
}

try {
  initialize();
} catch (error) {
  document.documentElement.classList.remove("enhanced");
  document.querySelector("#enhancement-error").hidden = false;
  console.error("Story enhancements failed:", error);
}
