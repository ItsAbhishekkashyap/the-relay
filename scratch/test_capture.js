const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

async function test() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  console.log('Launching Chrome from:', chromePath);
  
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1600,1050'],
    defaultViewport: {
      width: 1600,
      height: 1050,
      deviceScaleFactor: 2,
    }
  });

  try {
    const page = await browser.newPage();
    console.log('Navigating to https://the-relay-navy.vercel.app/ ...');
    await page.goto('https://the-relay-navy.vercel.app/', { waitUntil: 'networkidle0', timeout: 30000 });
    console.log('Page loaded! Title:', await page.title());

    const outDir = path.resolve(__dirname, '../reports/assets');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

    const testShot = path.join(outDir, 'test_initial_load.png');
    await page.screenshot({ path: testShot, fullPage: false });
    console.log('Screenshot saved to:', testShot);
  } finally {
    await browser.close();
  }
}

test().catch(err => {
  console.error('Error in test:', err);
  process.exit(1);
});
