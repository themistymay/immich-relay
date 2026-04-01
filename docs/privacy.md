---
layout: default
title: Privacy Policy
---

# Privacy Policy

**Project:** immich-relay
**Last updated:** 2026-04-01

---

## Overview

immich-relay synchronizes albums from an Immich instance to Google Photos. This policy describes what data immich-relay accesses, how it is used, and how it is protected — whether you run the software yourself or use a hosted version operated on your behalf.

---

## Data Accessed and Processed

To provide the sync service, immich-relay accesses and processes the following data:

| Data | Purpose |
|---|---|
| Google OAuth token | Authorize requests to the Google Photos API on your behalf |
| Google Photos albums and media | Read app-uploaded media; upload and remove synced photos |
| Immich server URL and API key | Connect to your Immich instance to read albums and download assets |
| Photos and videos | Downloaded from Immich and uploaded to Google Photos as part of the sync |
| Sync state | Track which assets have been synced to avoid duplicates and detect removals |

Photos and videos are processed transiently — they are not retained after upload to Google Photos. Credentials and sync state are retained only as long as necessary to operate the service for you.

---

## How Your Data Is Used

User data is used **solely** to perform the photo sync you have configured and authorized. Specifically:

- Google account data is used only to upload photos to, and remove photos from, your Google Photos library.
- Immich credentials are used only to read your Immich albums and download assets for sync.
- No data is used for advertising, analytics, profiling, or any purpose unrelated to the sync service.

---

## Google API Limited Use Compliance

The use of information received from Google Photos APIs will adhere to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the [Limited Use requirements](https://developers.google.com/terms/api-services-user-data-policy#additional_requirements_for_specific_api_scopes).

Google user data obtained through the Photos Library API:

- Is used **only** to sync your photos from your Immich instance into your own Google Photos library.
- Is **never** transferred or sold to third parties, advertising platforms, data brokers, or information resellers.
- Is **never** used for serving ads, retargeting, or interest-based advertising.
- Is **never** used to determine credit-worthiness or for lending purposes.
- Is **never** used to create, train, or improve any machine learning or artificial intelligence model.
- Is **never** read by humans except as required to investigate abuse, comply with applicable law, or with your explicit consent.

---

## Data Sharing

User data is not sold, rented, or shared with third parties except as follows:

- **Google Photos API** — photos and album commands are sent to Google in order to perform the sync. This is governed by [Google's Privacy Policy](https://policies.google.com/privacy).
- **Your Immich instance** — album and asset data is read from the Immich server you configure.
- **Legal requirements** — data may be disclosed if required by law or to protect against fraud or abuse.

No other sharing occurs.

---

## Google Photos OAuth Scopes

immich-relay requests only the minimum scopes required to function:

| Scope | Purpose |
|---|---|
| `photoslibrary.appendonly` | Upload photos synced from Immich |
| `photoslibrary.edit.appcreateddata` | Remove photos that were deleted in Immich |
| `photoslibrary.readonly.appcreateddata` | Check which photos the app has already uploaded |

No other Google account data is accessed.

---

## Data Retention

- **Photos and videos** are not retained. They are deleted immediately after upload to Google Photos.
- **OAuth tokens and credentials** are retained for as long as your account is active or until you revoke access.
- **Sync state** is retained for as long as necessary to operate the sync accurately.

You can revoke Google access at any time from your [Google Account permissions page](https://myaccount.google.com/permissions).

---

## Children's Privacy

immich-relay is not directed at children under 13 and does not knowingly collect data from children.

---

## Changes to This Policy

If this policy is updated, the "Last updated" date at the top will change. You can review the full history of changes in the [repository's commit log](https://github.com/themistymay/immich-relay/commits/main/docs/privacy.md).

---

## Contact

For questions or concerns, open an issue at https://github.com/themistymay/immich-relay/issues.
