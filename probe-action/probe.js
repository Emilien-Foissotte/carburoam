const puppeteer = require("puppeteer");
const TARGET_URL = "https://carburoam.streamlit.app/";
const WAKE_UP_BUTTON_TEXT = "app back up";
const PAGE_LOAD_GRACE_PERIOD_MS = 10000;
const TIMEOUT_MS = 30000;

console.log(process.version);

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    ignoreHTTPSErrors: true,
    args: ["--no-sandbox"],
  });

  const page = await browser.newPage();
  console.log(page); // Print the page object to inspect its properties

  await page.goto(TARGET_URL);

  console.log(page); // Print the page object to inspect its properties

  // Wait a grace period for the application to load
  await page.waitForTimeout(PAGE_LOAD_GRACE_PERIOD_MS);

  const checkForHibernation = async (target) => {
    // Look for any buttons containing the target text of the reboot button
    const [button] = await target.$x(
      `//button[contains(., '${WAKE_UP_BUTTON_TEXT}')]`,
    );
    if (button) {
      console.log("App hibernating. Attempting to wake up!");
      await button.click();
    } else if (
      await target.evaluate(() => document.body.innerText.includes("Carburoam"))
    ) {
      console.log("App is already up and running with 'Carburoam' displayed!");
    } else {
      console.log("App is already up and running!");
    }
  };

  let foundCarburoam = false;
  const startTime = Date.now();
  while (!foundCarburoam) {
    const frames = await page.frames();
    for (const frame of frames) {
      if (
        await frame.evaluate(() =>
          document.body.innerText.includes("Carburoam"),
        )
      ) {
        foundCarburoam = true;
        console.log("Success: Found 'Carburoam' in the page!");
        break;
      }
    }

    if (Date.now() - startTime > TIMEOUT_MS) {
      console.error("Error: Timeout exceeded. No frame contains 'Carburoam'.");
      process.exit(1);
    }

    await page.waitForTimeout(1000); // Wait 1 second before checking again
  }

  await browser.close();
})();
