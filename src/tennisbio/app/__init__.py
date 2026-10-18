"""The local application «Tennisbio» (docs/aplicacion_local.md): the layer around the analysis that the
user opens and never has to watch. It does not analyse anything itself: it keeps an index of videos,
matches, players and analyses, runs the existing idempotent stages from a queue, builds each analysis's
report as a new version, audits it, compares it with the previous one and only replaces that one when
nothing got worse. Part 1 (this package): the core, without a window.

    db        the index (SQLite), rebuilt from the folders when it is lost or damaged
    videos    adding a video: identity by content, proposal of its data, the corner cases
    storage   free disk, what is regenerable, the guard before a heavy job
    quality   versions of an analysis, its audit and the comparison with the previous one
    jobs      the queue, the runner and the response to every error
"""
