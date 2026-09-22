"""One-time backfills from platform data exports.

An export is the only way to recover favourites you saved before this library
existed. What comes back is thin -- a link and a date, nothing else -- so every
imported item starts unresolved and is filled in later by
:mod:`favorites.backfill`.
"""
