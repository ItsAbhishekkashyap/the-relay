const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUTPUT_DIR = path.resolve(__dirname, '../reports/assets');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function capture() {
  console.log('Launching Chrome...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1680,1050'],
    defaultViewport: {
      width: 1680,
      height: 1050,
      deviceScaleFactor: 2,
    },
  });

  const page = await browser.newPage();
  page.setDefaultTimeout(45000);

  try {
    console.log('Navigating to app...');
    await page.goto('https://the-relay-navy.vercel.app/', { waitUntil: 'networkidle0' });
    await sleep(2000);

    // --------------------------------------------------------------------------
    // C.4: Experiment Analytics Dashboard
    // --------------------------------------------------------------------------
    console.log('Navigating to Experiments...');
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.trim().startsWith('Experiments')) {
        console.log('Clicking Experiments nav item...');
        await btn.click();
        break;
      }
    }

    console.log('Waiting for Experiments page content...');
    await page.waitForFunction(
      () => document.body.innerText.includes('Experiment Analytics') ||
            document.body.innerText.includes('Empirical Measurements'),
      { timeout: 20000 }
    );
    await sleep(3500);

    const c4Path = path.join(OUTPUT_DIR, 'C4_experiment_analytics_dashboard.png');
    await page.screenshot({ path: c4Path });
    console.log('Saved C.4 to:', c4Path);

    // --------------------------------------------------------------------------
    // C.5: Simulator Controls
    // --------------------------------------------------------------------------
    console.log('Navigating to Settings (Simulator Controls)...');
    const navButtons = await page.$$('button');
    for (const btn of navButtons) {
      const text = await page.evaluate(el => el.innerText, btn);
      if (text && text.trim().startsWith('Settings')) {
        console.log('Clicking Settings nav item...');
        await btn.click();
        break;
      }
    }

    console.log('Waiting for Settings / Simulator page content...');
    await page.waitForFunction(
      () => document.body.innerText.includes('Simulator Control') ||
            document.body.innerText.includes('Base Delay') ||
            document.body.innerText.includes('Calibrated Baseline') ||
            document.body.innerText.includes('Failure Injection'),
      { timeout: 20000 }
    );
    await sleep(3500);

    const c5Path = path.join(OUTPUT_DIR, 'C5_simulator_controls.png');
    await page.screenshot({ path: c5Path });
    console.log('Saved C.5 to:', c5Path);

    console.log('C.4 and C.5 captured successfully!');
  } finally {
    await browser.close();
  }
}

capture().catch(err => {
  console.error('Error during capture:', err);
  process.exit(1);
});
