# Footprint · Email and phone lookup — Design

**Status:** approved design, implemented on `claude/nice-shannon-8av41v`
**Date:** 2026-11-17
**Depends on:** Footprint (danfox127-dotcom/TikTokAnalyzer#45 — shipped)

## 1. Purpose

Footprint finds where a *username* exists. This adds lookup by **email address**
and **phone number** — "see what those are linked to" — for the same audiences:
brands checking their own footprint and impersonation risk, and people auditing
their own exposure. The scope was left to the builder ("decide how
comprehensive this can be"); the calls below were stated to the user before
building.

## 2. Goals, non-goals, anti-goals

**Goals**
- An email address → the accounts it is *publicly* linked to, with how each
  link is known and how strong it is.
- An email address → whether email from its domain can be faked, in plain
  words, with the fix.
- A phone number → what the number says about itself.
- The brand report gains the email-faking check and the website's phone numbers.

**Non-goals**
- Deep people-search: no data brokers, no breach databases via API.

**Anti-goals** (would make this a failure even if it worked)
- Probing sign-up or password-reset flows to see whether an address or number
  has an account somewhere (the holehe approach): it misuses account-recovery
  systems, can send the person a reset alert, breaks those sites' terms, and is
  mostly used to target individuals.
- Naming a phone number's owner, or checking messaging apps for a number.
- Keeping any record of what was looked up.

## 3. Approaches considered

1. **Consent-based sources only (chosen).** Gravatar (profiles and verified
   accounts the owner published), GitHub commits made with the address,
   WebFinger on the address's own domain, public DNS for mail records, and
   offline phone parsing. Fewer hits, but every link is one the owner put out.
2. **Account-existence probing** (sign-up / password-reset checks across many
   sites). Far more hits, but it is the anti-goal above.
3. **Paid enrichment APIs** (people-search, carrier lookup, breach search).
   Costs money, needs keys, and is data-broker territory for individuals.

## 4. What was built

- `footprint/mailcheck.py` — MX, SPF and DMARC via Google's DNS-over-HTTPS
  (`dns.google`). Only the domain is sent. A failed lookup is *unknown*, never
  *open*; a missing domain says so. DMARC is inherited from parent domains
  (`sp=` where set); `pct` below 100 is *partly protected*. Verdicts:
  protected / partly / watching / open / no_domain / unknown.
- `footprint/phone.py` — `phonenumbers` (libphonenumber data), offline: validity,
  formats, line type, country and prefix area, first carrier, time zone (hidden
  when a number spans more than three). Numbers without `+` are read as
  `FOOTPRINT_PHONE_REGION` (default US). Degrades to a message without the package.
- `footprint/lookup.py` — `kind()` (email / phone / username); Gravatar by
  SHA-256; GitHub commit search by `author-email` (accounts GitHub tied to the
  address are *verified*; a repo owner holding most unlinked commits is
  *likely*); WebFinger on the address's domain, skipped for big webmail
  providers. Linked URLs map to known sites with `brand.profile_from_link`, then
  `profile.fetch` + `match.fingerprint` + `match.assess`. `run()` streams
  events `kind, mail, gravatar, github, fediverse, linked, details, match,
  handles, done` (or `kind, phone, done`).
- `footprint/app.py` — `/lookup` page and `/lookup/stream` (SSE); the search box
  and `/?u=` send emails and phone numbers to Look up.
- `footprint/brand.py` — a `mail` event and finding for the website's domain;
  phone numbers from the website's `tel:` links, with invalid ones flagged.

## 5. Calls made by the builder

- Webmail domains (gmail.com etc.) get "personal webmail" instead of a faking
  verdict: the setting belongs to the provider, not the person.
- Shared-inbox local parts (hello@, info@, support@…) are not offered as a
  username guess.
- The breach-check link goes to Have I Been Pwned's home page, not a URL
  carrying the address.
- GitHub's user search by email was dropped: it returns fuzzy, unrelated users.

## 6. Verification

- Unit tests with mocked responses: `tests/test_footprint_mailcheck.py`,
  `tests/test_footprint_lookup.py`, plus additions to the app and brand tests.
- Live from the cloud box: Gravatar's public demo profile (found, with four
  verified accounts), DMARC for several real domains, GitHub commit search.
- Screenshots of the Look up page (desktop dark, phone light, no sideways
  scroll at 390 px) and the brand report's new section.
