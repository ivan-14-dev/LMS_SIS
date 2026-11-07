const fs = require('fs');
const { createHash, createHmac, randomUUID } = require('crypto');
const { expect } = require('@playwright/test');

/*
 * This suite requires a fresh, disposable validation.localhost stack, not the shared installation.
 * SIS_LMS_GRADE_E2E_FIXTURE points to JSON with isolated:true, baseUrl, and variants keyed by SIS mode.
 * Each variant requires evaluationId, evaluationTitle, learnerId, learnerMatricule, lmsUsername,
 * courseId, subsectionId, webhookSecretEnv. The named environment variable contains WEBHOOK_SECRET.
 * Seed an open non-anonymous continuous-assessment /20 evaluation and its authorized learner,
 * active SIS/LMS user/course/enrollment
 * mappings, and active assessment mapping. There must be no existing notes or LMS proposals.
 * SIS_E2E_CREDENTIALS uses the existing {username,password} format for authorized staff in both tenants.
 * A real Celery worker (or real eager task execution) must process the signed grade.updated webhook.
 */
function loadGradeFixture(variant) {
  if (process.env.SIS_LMS_GRADE_E2E_ISOLATED !== '1') {
    throw new Error('Refusing mutations: set SIS_LMS_GRADE_E2E_ISOLATED=1 only for a disposable validation stack.');
  }
  if (!process.env.SIS_E2E_URL || !process.env.SIS_LMS_GRADE_E2E_FIXTURE || !process.env.SIS_E2E_CREDENTIALS) {
    throw new Error('Required: SIS_E2E_URL, SIS_LMS_GRADE_E2E_FIXTURE, and SIS_E2E_CREDENTIALS.');
  }
  const origin = new URL(process.env.SIS_E2E_URL);
  if (!['http:', 'https:'].includes(origin.protocol)
    || !/^(?:[a-z0-9-]+\.)?validation\.localhost$/.test(origin.hostname)
    || Number(origin.port) <= 1024) {
    throw new Error('Grade review requires an explicit disposable validation.localhost port above 1024.');
  }
  const config = JSON.parse(fs.readFileSync(process.env.SIS_LMS_GRADE_E2E_FIXTURE, 'utf8'));
  if (config.isolated !== true || new URL(config.baseUrl).origin !== origin.origin) {
    throw new Error('Fixture must declare isolated:true and baseUrl matching SIS_E2E_URL.');
  }
  const fixture = config.variants?.[variant];
  if (!fixture || !['evaluationId', 'learnerId'].every(field => Number.isInteger(fixture[field]) && fixture[field] > 0)
    || ![
      'evaluationTitle', 'learnerMatricule', 'lmsUsername', 'courseId', 'subsectionId', 'webhookSecretEnv',
    ].every(field => typeof fixture[field] === 'string' && fixture[field].trim())) {
    throw new Error(`Missing ${variant} grade fixture fields; see e2e/lms-grade-review-fixture.js.`);
  }
  const secret = process.env[fixture.webhookSecretEnv];
  if (!secret) { throw new Error(`Missing isolated webhook secret environment variable: ${fixture.webhookSecretEnv}`); }
  const credentials = JSON.parse(fs.readFileSync(process.env.SIS_E2E_CREDENTIALS, 'utf8'));
  if (!credentials.username || !credentials.password) { throw new Error('Staff credentials require username and password.'); }
  origin.hostname = `${variant}.validation.localhost`;
  return {
    fixture, credentials, secret, apiOrigin: origin.origin,
  };
}

function gradeEvent(fixture, score) {
  const eventId = randomUUID();
  return {
    eventId,
    storedEventId: createHash('sha256').update(eventId).digest('hex'),
    body: JSON.stringify({
      user: { username: fixture.lmsUsername },
      course: { course_key: fixture.courseId },
      subsection_id: fixture.subsectionId,
      score,
      max_score: '20',
      timestamp: new Date().toISOString(),
    }),
  };
}

async function deliverGrade(request, environment, event) {
  const response = await request.post(`${environment.apiOrigin}/api/v1/integration/webhook/lms/`, {
    data: event.body,
    headers: {
      'Content-Type': 'application/json',
      'X-Event-Type': 'grade.updated',
      'X-Event-ID': event.eventId,
      'X-Signature': createHmac('sha256', environment.secret).update(event.body).digest('hex'),
    },
    maxRedirects: 0,
  });
  expect(response.status(), await response.text()).toBe(200);
  expect(await response.json()).toMatchObject({ status: 'queued', event: 'grade.updated' });
}

async function waitForProposal(api, evaluationId, event) {
  let proposal;
  await expect.poll(async () => {
    const result = await api(`notes/evaluations/${evaluationId}/propositions_lms/?page_size=25`);
    expect(result.next, 'Fresh isolated evaluation must fit one visible proposal page.').toBeNull();
    proposal = result.results.find(item => item.event_id === event.storedEventId);
    return proposal?.review_status;
  }, {
    timeout: 45000,
    intervals: [1000, 2000, 3000],
    message: 'A real worker must consume the webhook using the seeded active LMS mappings.',
  }).toBe('pending');
  return proposal;
}

module.exports = {
  loadGradeFixture, gradeEvent, deliverGrade, waitForProposal,
};
