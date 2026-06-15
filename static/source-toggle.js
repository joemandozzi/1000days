document.querySelectorAll('.source-toggle').forEach(function(toggle) {
  toggle.addEventListener('click', function(e) {
    var btn = e.target.closest('.source-btn');
    if (!btn) return;

    var work   = btn.dataset.work;
    var source = btn.dataset.source;

    // Swap active button
    toggle.querySelectorAll('.source-btn').forEach(function(b) {
      b.classList.toggle('is-active', b === btn);
    });

    // Swap visible panel
    var local    = document.getElementById(work + '-panel-local');
    var external = document.getElementById(work + '-panel-external');
    if (local)    local.classList.toggle('source-panel--hidden', source !== 'local');
    if (external) external.classList.toggle('source-panel--hidden', source !== 'external');
  });
});
