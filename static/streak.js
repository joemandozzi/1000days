/**
 * Streak counter — the only JavaScript on this site.
 *
 * State stored in localStorage:
 *   bradbury_streak      : number  — current consecutive-night count
 *   bradbury_last_read   : string  — ISO date of last completed night ("2026-06-10")
 *
 * A "night" is marked complete when the user clicks the button on any given
 * calendar date. Clicking again on the same date is a no-op (idempotent).
 * Missing a day resets the streak to 1 on the next read night.
 */

(function () {
  const STREAK_KEY = "bradbury_streak";
  const LAST_KEY   = "bradbury_last_read";

  function today() {
    // Use the date embedded in the page so the streak aligns with the
    // server-side date even if the visitor is in a different timezone.
    const el = document.querySelector("[data-date]");
    return el ? el.dataset.date : new Date().toISOString().slice(0, 10);
  }

  function daysBetween(a, b) {
    // Both are ISO strings "YYYY-MM-DD". Returns integer days (b - a).
    return Math.round((new Date(b) - new Date(a)) / 86400000);
  }

  function getState() {
    return {
      streak: parseInt(localStorage.getItem(STREAK_KEY) || "0", 10),
      last:   localStorage.getItem(LAST_KEY) || null,
    };
  }

  function renderStreak(streak) {
    const el = document.getElementById("streak-display");
    if (!el) return;
    if (streak === 0) {
      el.textContent = "Start your 1,000 nights tonight.";
    } else {
      el.textContent = `Night ${streak} of 1,000`;
    }
  }

  function markRead() {
    const t = today();
    const { streak, last } = getState();

    if (last === t) return; // already marked today

    let newStreak;
    if (!last) {
      newStreak = 1;
    } else {
      const gap = daysBetween(last, t);
      newStreak = gap === 1 ? streak + 1 : 1; // consecutive = +1, gap = reset
    }

    localStorage.setItem(STREAK_KEY, String(newStreak));
    localStorage.setItem(LAST_KEY, t);
    renderStreak(newStreak);

    const btn = document.getElementById("mark-read-btn");
    if (btn) {
      btn.textContent = "✓ Night complete";
      btn.disabled = true;
    }
  }

  // On load: show current streak and disable button if already read today.
  document.addEventListener("DOMContentLoaded", function () {
    const { streak, last } = getState();
    renderStreak(streak);

    const btn = document.getElementById("mark-read-btn");
    if (btn) {
      if (last === today()) {
        btn.textContent = "✓ Night complete";
        btn.disabled = true;
      } else {
        btn.addEventListener("click", markRead);
      }
    }
  });
})();
