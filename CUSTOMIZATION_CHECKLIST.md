# Client customization checklist

Use this for every delivery. Never deploy the BrightHome sample unchanged for a real business.

## 1. Collect and approve

- [ ] Business name, public contact details, website, service area, and opening hours
- [ ] Brand colors and logo usage permission
- [ ] Exact service descriptions and exclusions
- [ ] Pricing language the client explicitly approves
- [ ] Booking, cancellation, rescheduling, refund, guarantee, and access policies
- [ ] Quote form fields and the person/system that receives new leads
- [ ] Privacy notice, retention period, and consent wording
- [ ] Ten common customer questions plus approved answers
- [ ] Hosting account, domain/subdomain, and client-owned OpenAI API key if AI mode is purchased

## 2. Configure

- [ ] Replace `data/business.json`
- [ ] Replace `data/knowledge_base.json`
- [ ] Replace all BrightHome copy and example.com links in the demo site
- [ ] Set a unique, randomly generated `ADMIN_TOKEN`
- [ ] Set `APP_ENV=production` on the public host
- [ ] Configure `LEAD_WEBHOOK_URL` if included in the package
- [ ] Set `STORE_CONVERSATIONS` according to the client's privacy decision
- [ ] Configure exact `CORS_ORIGINS` only when required
- [ ] Initialize a fresh production database

## 3. Verify

- [ ] Ask every supplied FAQ in at least two phrasings
- [ ] Ask an out-of-scope question and confirm the assistant does not invent an answer
- [ ] Try prompt-injection wording and confirm the response stays within approved facts
- [ ] Submit one valid lead by email and another by phone
- [ ] Confirm consent is required and invalid emails are rejected
- [ ] Confirm webhook/CRM delivery, if configured
- [ ] Log in with the correct admin token and reject a wrong token
- [ ] Edit, disable, add, and delete a test knowledge article
- [ ] Export leads and open the CSV safely
- [ ] Check phone, tablet, desktop, keyboard navigation, and visible focus
- [ ] Confirm HTTPS, persistent storage, backups, and health monitoring
- [ ] Confirm the public host uses exactly one replica while SQLite is enabled

## 4. Handoff

- [ ] Remove all test leads and conversations from the production database
- [ ] Give the client their deployment URL, admin URL, and token through separate secure channels
- [ ] Provide a short screen recording of lead review and knowledge editing
- [ ] Record the hosting renewal date and API billing owner
- [ ] Get written acceptance of the final approved answers
- [ ] State the support period and what counts as a paid change request
