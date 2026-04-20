(function () {
  function setError(el, message) {
    if (!el) return;
    if (message) {
      el.hidden = false;
      el.textContent = message;
    } else {
      el.hidden = true;
      el.textContent = "";
    }
  }

  function renderFooter(data) {
    var root = document.getElementById("app-footer");
    if (!root) return;

    var versionEl = document.getElementById("app-version");
    var bannerEl = document.getElementById("update-banner");
    var errEl = document.getElementById("footer-error");

    if (versionEl && data.app_version != null) {
      versionEl.textContent = "Version " + data.app_version;
    }

    setError(errEl, data.error ? "Could not check for updates: " + data.error : "");

    if (!bannerEl) return;

    if (data.update_available && data.release_url && data.latest_version) {
      bannerEl.hidden = false;
      bannerEl.innerHTML = "";
      var a = document.createElement("a");
      a.href = data.release_url;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      a.textContent = "Version " + data.latest_version + " is available on GitHub";
      bannerEl.appendChild(document.createTextNode("Update available: "));
      bannerEl.appendChild(a);
      bannerEl.appendChild(document.createTextNode("."));
    } else {
      bannerEl.hidden = true;
      bannerEl.textContent = "";
    }
  }

  function load() {
    fetch("/api/update-check")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(renderFooter)
      .catch(function () {
        var errEl = document.getElementById("footer-error");
        setError(errEl, "Could not load version information.");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
