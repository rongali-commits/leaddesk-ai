# Buyer delivery guide

## What you received

Your website assistant answers common questions using the information your business approved. Visitors can submit a structured quote request, and authorized staff can review leads, update their status, export them, and improve the approved-answer library.

## Daily workflow

1. Open `/admin` on your deployed LeadDesk URL.
2. Enter the admin token supplied securely during handoff.
3. Review new and qualified leads, then change each status as you follow up.
4. Check Conversations for unanswered questions.
5. Add or improve an approved answer in Knowledge when visitors repeatedly ask something new.

## Important boundaries

- The assistant does not confirm appointments or collect payments.
- It can only be as accurate as the approved information provided to it.
- Never add confidential information to the knowledge base.
- Do not paste the admin token or API key into website content.
- Contact your implementer before changing hosting, domain, or storage settings.

## Backup

The default database is the file configured by `DATABASE_PATH`. Back up that file using your hosting provider's persistent-volume backup feature. Test restoration before relying on the backup.

## Troubleshooting

- **Chat answers but sounds less conversational:** The app is probably in deterministic mode or has automatically failed over. Check `/health`, API billing, and the server-side API key.
- **A lead is not in the CRM:** It is still stored locally. Check the admin lead inbox, then inspect the webhook URL and automation history.
- **New JSON answers are not visible:** After first run, knowledge is managed in SQLite. Use the admin Knowledge screen, or initialize a fresh database only during a planned migration.
- **Admin access fails:** Confirm the current server `ADMIN_TOKEN`; the token is case-sensitive.

