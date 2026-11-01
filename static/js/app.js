// Image previews, per-file removal, and drag-and-drop for the publish/edit forms.
document.querySelectorAll("[data-image-input]").forEach((input) => {
  const form = input.closest("form");
  const preview = form ? form.querySelector("[data-image-preview]") : null;
  if (!preview) return;

  const removeLabel = preview.dataset.removeLabel || "Remove";
  let files = [];

  const syncInput = () => {
    if (typeof DataTransfer === "undefined") return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
  };

  const render = () => {
    preview.innerHTML = "";
    files.forEach((file, index) => {
      const item = document.createElement("div");
      item.className = "image-preview__item";

      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.alt = file.name;
      img.onload = () => URL.revokeObjectURL(img.src);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "image-preview__remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `${removeLabel}: ${file.name}`);
      remove.addEventListener("click", () => {
        files.splice(index, 1);
        syncInput();
        render();
      });

      item.append(img, remove);
      preview.append(item);
    });
  };

  input.addEventListener("change", () => {
    files = Array.from(input.files);
    render();
  });

  const zone = input.closest(".upload-zone");
  if (zone) {
    ["dragenter", "dragover"].forEach((name) => {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach((name) => {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragover");
      });
    });
    zone.addEventListener("drop", (event) => {
      const dropped = event.dataTransfer
        ? Array.from(event.dataTransfer.files)
        : [];
      if (!dropped.length) return;
      files = files.concat(dropped);
      syncInput();
      render();
    });
  }
});

// Confirmation dialogs for destructive actions.
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

// Dismissible flash messages.
document.querySelectorAll(".flash__close").forEach((button) => {
  button.addEventListener("click", () => {
    const flash = button.closest(".flash");
    if (flash) flash.remove();
  });
});

// Detail gallery thumbnails.
document.querySelectorAll(".detail-thumb").forEach((thumb) => {
  thumb.addEventListener("click", () => {
    const main = document.getElementById("detail-main-image");
    if (main) main.src = thumb.dataset.imageSrc;
    thumb.parentElement
      .querySelectorAll(".detail-thumb")
      .forEach((item) => item.classList.remove("is-active"));
    thumb.classList.add("is-active");
  });
});

// Mobile navigation.
const navToggle = document.querySelector("[data-nav-toggle]");
const primaryNav = document.getElementById("primary-nav");
if (navToggle && primaryNav) {
  navToggle.addEventListener("click", () => {
    const open = primaryNav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
}

// Home carousel.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

document.querySelectorAll("[data-carousel]").forEach((carousel) => {
  const slides = Array.from(carousel.querySelectorAll("[data-slide]"));
  const dots = Array.from(carousel.querySelectorAll("[data-dot]"));
  if (!slides.length) return;

  let index = 0;
  let timer = null;

  const show = (next) => {
    index = (next + slides.length) % slides.length;
    slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
    dots.forEach((dot, i) => {
      const active = i === index;
      dot.classList.toggle("is-active", active);
      dot.setAttribute("aria-pressed", String(active));
    });
  };

  const stop = () => {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  };

  const start = () => {
    stop();
    if (!reducedMotion) {
      timer = window.setInterval(() => show(index + 1), 6000);
    }
  };

  dots.forEach((dot, i) => {
    dot.addEventListener("click", () => {
      show(i);
      start();
    });
  });

  carousel.addEventListener("mouseenter", stop);
  carousel.addEventListener("mouseleave", start);
  carousel.addEventListener("focusin", stop);
  carousel.addEventListener("focusout", start);
  carousel.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      show(index - 1);
      start();
    } else if (event.key === "ArrowRight") {
      show(index + 1);
      start();
    }
  });

  show(0);
  start();
});

// Auto-dismiss success and info flashes after a few seconds.
window.setTimeout(() => {
  document.querySelectorAll(".flash--success, .flash--info").forEach((flash) => {
    flash.remove();
  });
}, 6000);
