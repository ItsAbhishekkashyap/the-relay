const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUTPUT_DIR = path.resolve(__dirname, '../reports/assets');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function captureAll() {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  console.log('Launching Chrome from:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=1680,1050',
    ],
    defaultViewport: {
      width: 1680,
      height: 1050,
      deviceScaleFactor: 2,
    },
  });

  const page = await browser.newPage();
  page.setDefaultTimeout(60000);

  try {
    // --------------------------------------------------------------------------
    // C.1: Research Chat Interface
    // --------------------------------------------------------------------------
    console.log('Step 1: Navigating to Chat page...');
    await page.goto('https://the-relay-navy.vercel.app/', { waitUntil: 'networkidle0' });
    await sleep(2000);

    console.log('Step 2: Submitting BLEU score research question...');
    // Click the first suggested query button: "What BLEU score did the Transformer base model achieve on English-to-German?"
    const suggestedButtons = await page.$$('button');
    let clickedSuggested = false;
    for (const btn of suggestedButtons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.includes('What BLEU score')) {
        console.log('Found suggested button, clicking...');
        await btn.click();
        clickedSuggested = true;
        break;
      }
    }

    if (!clickedSuggested) {
      console.log('Manually typing question into textarea...');
      const textarea = await page.$('textarea');
      await textarea.type('What BLEU score did the Transformer base model achieve on English-to-German translation in Attention Is All You Need?');
      const submitBtn = await page.$('button[type="submit"]');
      await submitBtn.click();
    }

    console.log('Waiting for research assistant response...');
    // Wait for the response AnswerCard or status badge
    await page.waitForFunction(
      () => document.body.innerText.includes('Verified Provenance') || 
            document.body.innerText.includes('According to the retrieved research') ||
            document.body.innerText.includes('Attention Is All You Need'),
      { timeout: 45000 }
    );
    await sleep(2000);

    const c1Path = path.join(OUTPUT_DIR, 'C1_research_chat_interface.png');
    await page.screenshot({ path: c1Path });
    console.log('Saved C.1 to:', c1Path);

    // --------------------------------------------------------------------------
    // C.2: Evidence and Citation Display
    // --------------------------------------------------------------------------
    console.log('Step 3: Expanding Evidence Panel for C.2...');
    // Find and click the evidence expand button (e.g. "Retrieved Evidence (5 passages)")
    const buttons = await page.$$('button');
    let clickedEvidence = false;
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && (text.includes('Evidence') || text.includes('passages') || text.includes('Retrieved Evidence'))) {
        console.log('Found evidence toggle button:', text);
        await btn.click();
        clickedEvidence = true;
        break;
      }
    }

    await sleep(1500);

    // Scroll down slightly so evidence passages are in full view
    await page.evaluate(() => {
      window.scrollBy({ top: 400, behavior: 'smooth' });
    });
    await sleep(1500);

    const c2Path = path.join(OUTPUT_DIR, 'C2_evidence_and_citation_display.png');
    await page.screenshot({ path: c2Path });
    console.log('Saved C.2 to:', c2Path);

    // --------------------------------------------------------------------------
    // C.3: System Monitoring Dashboard
    // --------------------------------------------------------------------------
    console.log('Step 4: Navigating to System Overview...');
    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(500);

    // Click "System Overview" in sidebar
    const navButtons = await page.$$('button');
    for (const btn of navButtons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.includes('System Overview')) {
        console.log('Clicking System Overview nav...');
        await btn.click();
        break;
      }
    }

    await sleep(3000);
    // Wait for metrics to render
    await page.waitForFunction(
      () => document.body.innerText.includes('SYSTEM TELEMETRY') || 
            document.body.innerText.includes('TrafficManager') ||
            document.body.innerText.includes('HEALTHY') ||
            document.body.innerText.includes('Queue Utilization'),
      { timeout: 20000 }
    );
    await sleep(2000);

    const c3Path = path.join(OUTPUT_DIR, 'C3_system_monitoring_dashboard.png');
    await page.screenshot({ path: c3Path });
    console.log('Saved C.3 to:', c3Path);

    // --------------------------------------------------------------------------
    // C.4: Experiment Analytics Dashboard
    // --------------------------------------------------------------------------
    console.log('Step 5: Navigating to Experiments Page...');
    for (const btn of await page.$$('button')) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.includes('Experiments')) {
        console.log('Clicking Experiments nav...');
        await btn.click();
        break;
      }
    }

    await sleep(3000);
    await page.waitForFunction(
      () => document.body.innerText.includes('BENCHMARK') || 
            document.body.innerText.includes('EXPERIMENTS') ||
            document.body.innerText.includes('Load Scenarios') ||
            document.body.innerText.includes('RRF'),
      { timeout: 20000 }
    );
    await sleep(2000);

    const c4Path = path.join(OUTPUT_DIR, 'C4_experiment_analytics_dashboard.png');
    await page.screenshot({ path: c4Path });
    console.log('Saved C.4 to:', c4Path);

    // --------------------------------------------------------------------------
    // C.5: Simulator Controls
    // --------------------------------------------------------------------------
    console.log('Step 6: Navigating to Settings (Simulator Controls)...');
    for (const btn of await page.$$('button')) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.includes('Settings')) {
        console.log('Clicking Settings nav...');
        await btn.click();
        break;
      }
    }

    await sleep(3000);
    await page.waitForFunction(
      () => document.body.innerText.includes('Simulator') || 
            document.body.innerText.includes('Baseline') ||
            document.body.innerText.includes('Jitter') ||
            document.body.innerText.includes('Calibration'),
      { timeout: 20000 }
    );
    await sleep(2000);

    const c5Path = path.join(OUTPUT_DIR, 'C5_simulator_controls.png');
    await page.screenshot({ path: c5Path });
    console.log('Saved C.5 to:', c5Path);

    console.log('ALL 5 APPLICATION SCREENSHOTS CAPTURED SUCCESSFULLY!');
  } finally {
    await browser.close();
  }
}

captureAll().catch(err => {
  console.error('Fatal error during capture:', err);
  process.exit(1);
});
