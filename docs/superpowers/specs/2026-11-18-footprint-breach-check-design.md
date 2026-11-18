# Footprint · Website breach check (Have I Been Pwned) — Design

**Status:** approved design, implemented on `claude/nice-shannon-8av41v`
**Date:** 2026-11-18
**Depends on:** Footprint email and phone lookup (danfox127-dotcom/TikTokAnalyzer#73 — shipped)

## Purpose

The user suggested the Have I Been Pwned (HIBP) API v3. The brand report gains one
question: has the brand's own website had a known data breach? A breach is what
people find when they search a brand's name with "breach", so it belongs next to
the email-faking and phone checks.

## Approaches and the choice

| Approach | What it adds | What it needs |
|---|---|---|
| **Free catalogue only (chosen by the user)** | Brand report: known breaches of the website's domain | Nothing; only the domain is sent |
| Free + email check | Look up: which breaches an address appears in | A paid HIBP API key |
| + domain search | Brand report: every breached address at the organisation | Domain verification with HIBP and a plan that covers it |

## What was built

- `footprint/breaches.py` — `for_domain()` calls `GET /api/v3/breaches?domain=` with
  a User-Agent naming the app (HIBP requires one). A subdomain with no breaches of
  its own is also checked under its parent. Failure is `checked: False` ("couldn't
  check"), never "no breaches". `describe()` gives one line per breach: title,
  month and year, accounts affected, what leaked, and HIBP's flags (not verified,
  believed fabricated, spam list).
- `footprint/brand.py` — a `breaches` event after `mail`; a warn finding listing
  up to five breaches, or a good finding when none is known; no finding when the
  check failed.
- Brand page and downloadable report — a "breaches" card in the
  "Email, phone and breaches" section, with HIBP's required credit and link
  (CC BY 4.0).

## Not done

- Searching breaches for an email address (needs a paid key). The Look up page
  keeps its link to HIBP for checking your own address.
- Domain search of an organisation's addresses.
- HIBP's logos (they'd break the report's no-outside-requests rule).

## Verification

- `tests/test_footprint_breaches.py`, brand and app tests (mocked).
- Live from the cloud environment: adobe.com, linkedin.com, canva.com return their
  catalogued breaches; shop.adobe.com falls back to adobe.com; sproutsocial.com
  returns none.
