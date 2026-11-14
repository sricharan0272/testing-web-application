const caseInfo = {
  TC01: ["Images", "1.1.1", "Text alternatives"],
  TC02: ["Form labels", "1.3.1", "Relationships"],
  TC03: ["Custom controls", "4.1.2", "Name, role, value"],
  TC04: ["Accessible names", "2.5.3", "Label in name"],
  TC05: ["Hidden content", "4.1.2", "Focusable content and hidden semantics"],
  TC06: ["Shadow DOM", "4.1.2", "Accessible name in a shadow root"],
  TC07: ["Live regions", "4.1.3", "Status message semantics"],
  TC08: ["Form errors", "3.3.1", "Error identification (interpretive)"],
  TC09: ["Tabs", "4.1.2", "Selected state"],
  TC10: ["Page title", "2.4.2", "Page title on SPA navigation"],
  TC11: ["Route focus", "2.4.3", "Focus after route change (interpretive)"],
  TC12: ["Dialog focus", "2.4.3", "Dialog focus management (interpretive)"],
  TC13: ["Focus visibility", "2.4.7", "Visible focus indicator"],
  TC14: ["Text contrast", "1.4.3", "Text contrast"]
};

const view = document.querySelector("#view");
const routeStatus = document.querySelector("#route-status");
const mainContent = document.querySelector("#main-content");
const titleSuffix = " | Accessibility Testing Research Lab";

function routeParts() {
  return window.location.hash.slice(1).split("/").filter(Boolean);
}

function updateNavigation(activePath) {
  document.querySelectorAll(".navigation a").forEach((link) => {
    if (link.hash === `#${activePath}`) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function caseLinks() {
  return Object.entries(caseInfo).map(([id, [label]]) => `
    <li>
      <a href="#/case/${id}/conforming">${id}: ${label} (conforming)</a>
      <a href="#/case/${id}/defective">${id}: ${label} (defective)</a>
    </li>
  `).join("");
}

function fixture(caseId, variant) {
  const defective = variant === "defective";
  switch (caseId) {
    case "TC01":
      return `<h2>Image alternatives</h2>
        <img class="sample-image informative-image" data-test-image="informative"
          src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='80'%3E%3Crect x='14' y='50' width='22' height='20' fill='%234b7bec'/%3E%3Crect x='49' y='34' width='22' height='36' fill='%234b7bec'/%3E%3Crect x='84' y='14' width='22' height='56' fill='%234b7bec'/%3E%3C/svg%3E"
          ${defective ? "" : 'alt="Bar chart with three blue bars increasing in height from left to right."'}>
        <img class="sample-image decorative-image" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='80'%3E%3Crect width='120' height='80' fill='%23f0b429'/%3E%3C/svg%3E" alt="">`.trim();
    case "TC02":
      return `<h2>Contact details</h2>
        ${defective ? '<label for="missing-email">Email address</label>' : '<label for="email">Email address</label>'}
        <input id="email" type="email" placeholder="name@example.test">`;
    case "TC03":
      return `<h2>Custom control</h2>
        ${defective
          ? '<div class="button-like" id="custom-action" data-activated="0">Run test</div>'
          : '<button id="custom-action" type="button" data-activated="0">Run test</button>'}
        <p id="activation-status" role="status">Not activated.</p>`;
    case "TC04":
      return `<h2>Search</h2>
        <button id="search-action" type="button" aria-label="${defective ? "Find" : "Search"}">Search</button>`;
    case "TC05":
      return `<h2>Visibility semantics</h2>
        <div ${defective ? 'aria-hidden="true"' : ""}>
          <button type="button" id="hidden-action" aria-label="Reveal details">Reveal details</button>
        </div>`;
    case "TC06":
      return `<h2>Web component</h2>
        <research-action></research-action>`;
    case "TC07":
      return `<h2>Status message</h2>
        <button id="save-action" type="button">Save item</button>
        <p id="status-message" ${defective ? "" : 'role="status" aria-live="polite"'}></p>`;
    case "TC08":
      return `<h2>Sign in</h2>
        <form id="error-form" novalidate>
          <label for="account-email">Email address</label>
          <input id="account-email" type="email" aria-invalid="true"
            ${defective ? "" : 'aria-describedby="email-error"'}>
          <p id="email-error">Enter a valid email address.</p>
        </form>`;
    case "TC09":
      return `<h2>Preferences</h2>
        <div role="tablist" aria-label="Preference categories">
          <button role="tab" id="tab-profile" aria-selected="true" aria-controls="panel-profile" tabindex="0">Profile</button>
          <button role="tab" id="tab-settings" aria-selected="false" aria-controls="panel-settings" tabindex="-1">Settings</button>
        </div>
        <section role="tabpanel" id="panel-profile" aria-labelledby="tab-profile">Profile preferences</section>
        <section role="tabpanel" id="panel-settings" aria-labelledby="tab-settings" hidden>Settings preferences</section>
        <button id="disclosure" type="button" aria-expanded="false" aria-controls="disclosure-panel">More details</button>
        <div id="disclosure-panel" hidden>Additional preference details.</div>`;
    case "TC10":
      return `<h2>Reports</h2><p>This view has a distinct page purpose.</p>`;
    case "TC11":
      return `<h2>Route focus</h2>
        <button id="focus-target" type="button">Focused route content</button>
        <a id="route-change" href="#/case/TC11/destination">Navigate to destination</a>`;
    case "TC12":
      return defective
        ? `<h2>Dialog focus</h2>
          <button id="dialog-opener" type="button">Open dialog</button>
          <div id="research-dialog" role="dialog" aria-labelledby="dialog-title" hidden>
            <h3 id="dialog-title">Research dialog</h3>
            <button id="dialog-close" type="button">Close dialog</button>
          </div>`
        : `<h2>Dialog focus</h2>
          <button id="dialog-opener" type="button">Open dialog</button>
          <dialog id="research-dialog" aria-labelledby="dialog-title">
            <h3 id="dialog-title">Research dialog</h3>
            <button id="dialog-close" type="button">Close dialog</button>
          </dialog>`;
    case "TC13":
      return `<h2>Keyboard focus</h2>
        <button id="focus-start" type="button">Start tab sequence</button>
        <button id="focus-visibility" class="${defective ? "no-focus-ring" : "focus-ring"}" type="button">Focus this control</button>`;
    case "TC14":
      return `<h2>Contrast sample</h2>
        <p id="contrast-sample" class="${defective ? "low-contrast" : "adequate-contrast"}">Readable sample text</p>`;
    default:
      return "<h2>Unknown test case</h2><p>Select a known case from the dashboard.</p>";
  }
}

function bindFixture(caseId, variant) {
  if (caseId === "TC03") {
    document.querySelector("#custom-action").addEventListener("click", (event) => {
      const count = Number(event.currentTarget.dataset.activated) + 1;
      event.currentTarget.dataset.activated = String(count);
      document.querySelector("#activation-status").textContent = `Activated ${count} times.`;
    });
  }
  if (caseId === "TC06") {
    const component = document.querySelector("research-action");
    const shadow = component.attachShadow({ mode: "open" });
    shadow.innerHTML = variant === "defective"
      ? '<button id="shadow-action" type="button"></button>'
      : '<button id="shadow-action" type="button">Open preferences</button>';
  }
  if (caseId === "TC07") {
    document.querySelector("#save-action").addEventListener("click", () => {
      document.querySelector("#status-message").textContent = "Item saved successfully.";
    });
  }
  if (caseId === "TC09") {
    document.querySelectorAll('[role="tab"]').forEach((tab) => {
      tab.addEventListener("click", () => {
        const selectedId = tab.id;
        const panels = document.querySelectorAll('[role="tabpanel"]');
        panels.forEach((panel) => {
          panel.hidden = panel.getAttribute("aria-labelledby") !== selectedId;
        });
        if (variant === "conforming") {
          document.querySelectorAll('[role="tab"]').forEach((item) => {
            item.setAttribute("aria-selected", String(item === tab));
            item.setAttribute("tabindex", item === tab ? "0" : "-1");
          });
        }
      });
    });
    const disclosure = document.querySelector("#disclosure");
    const panel = document.querySelector("#disclosure-panel");
    disclosure.addEventListener("click", () => {
      const expanded = panel.hidden;
      panel.hidden = !expanded;
      if (variant === "conforming") {
        disclosure.setAttribute("aria-expanded", String(expanded));
      }
    });
  }
  if (caseId === "TC12") {
    const dialog = document.querySelector("#research-dialog");
    document.querySelector("#dialog-opener").addEventListener("click", () => {
      if (variant === "conforming") {
        dialog.showModal();
      } else {
        dialog.hidden = false;
      }
    });
    document.querySelector("#dialog-close").addEventListener("click", () => {
      if (variant === "conforming") {
        dialog.close();
      } else {
        dialog.hidden = true;
      }
    });
  }
}

function renderRoute({ moveFocus = false } = {}) {
  const parts = routeParts();
  const requestedPath = parts[0] === "case" ? `/case/${parts[1]}` : `/${parts[0] || "dashboard"}`;
  const caseId = parts[0] === "case" ? parts[1] : null;
  const variant = parts[0] === "case" ? (parts[2] || "conforming") : null;

  if (caseId && caseId in caseInfo && ["conforming", "defective", "destination"].includes(variant)) {
    if (variant === "destination") {
      view.innerHTML = '<section class="panel"><h1 id="page-title">Destination</h1><p>New route content.</p></section>';
    } else {
      const [label, criterion, testPurpose] = caseInfo[caseId];
      view.innerHTML = `
        <section class="panel test-case" data-test-case="${caseId}" data-variant="${variant}" aria-labelledby="page-title">
          <p class="eyebrow">${caseId} · WCAG ${criterion} · ${testPurpose}</p>
          <h1 id="page-title">${label}: ${variant === "defective" ? "defective" : "conforming"} variant</h1>
          <div class="fixture">${fixture(caseId, variant)}</div>
          <p class="variant-note">Controlled research fixture. This example does not establish overall WCAG conformance.</p>
        </section>`;
      bindFixture(caseId, variant);
    }
    if (!(caseId === "TC10" && variant === "defective")) {
      document.title = `${caseId === "TC10" ? "Reports" : caseInfo[caseId][0]}${titleSuffix}`;
    }
    updateNavigation("/test-bed");
    if (caseId === "TC11" && variant !== "destination") {
      window.sessionStorage.setItem("tc11-variant", variant);
    }
  } else {
    const pages = {
      "/dashboard": {
        title: "Dashboard",
        description: "A controlled test bed for comparing accessibility checks based on the DOM and the browser Accessibility Tree.",
        details: [
          "Each test case offers conforming and defective variants through stable routes.",
          "The draft expected outcomes require independent manual and expert review before inferential analysis."
        ]
      },
      "/test-bed": {
        title: "Test bed",
        description: "Select a case to open its conforming variant. Use the variant route to inspect the paired defective example.",
        details: ["Both variants are served by the same SPA and can be loaded directly for reproducible automation."]
      },
      "/about": {
        title: "About this study",
        description: "The study examines whether DOM-based and Accessibility-Tree-based automated tests produce different results on identical content.",
        details: ["Automated checks cannot establish overall WCAG conformance."]
      }
    };
    const page = pages[requestedPath] || pages["/dashboard"];
    view.innerHTML = `
      <section class="panel" aria-labelledby="page-title">
        <h1 id="page-title">${page.title}</h1>
        <p>${page.description}</p>
        <ul>${page.details.map((detail) => `<li>${detail}</li>`).join("")}</ul>
        <h2>Test cases</h2><ul class="case-list">${caseLinks()}</ul>
      </section>`;
    document.title = `${page.title}${titleSuffix}`;
    updateNavigation(requestedPath);
  }

  routeStatus.textContent = document.querySelector("#page-title")?.textContent || "Page loaded";
  view.setAttribute("aria-busy", "false");
  if (moveFocus) {
    const currentParts = routeParts();
    const isRouteFocusDefect = currentParts[1] === "TC11" && currentParts[2] === "destination"
      && window.sessionStorage.getItem("tc11-variant") === "defective";
    if (!isRouteFocusDefect) {
      mainContent.focus({ preventScroll: true });
    }
  }
}

window.addEventListener("hashchange", () => renderRoute({ moveFocus: true }));
window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".navigation a").forEach((link) => {
    link.addEventListener("click", () => window.sessionStorage.removeItem("tc11-variant"));
  });
});
renderRoute();
document.documentElement.dataset.appReady = "true";
