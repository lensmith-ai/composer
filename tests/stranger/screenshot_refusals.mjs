// WebKit logs one CSP refusal of an inline stylesheet per frame while Playwright takes a screenshot: the style
// Playwright injects for the picture (measured on the app page: none without a screenshot, one per screenshot with
// one frame, two once the landed brief's frame is on the page; none in Chromium). The flow sets aside at most one
// such refusal per frame of each screenshot, only while that screenshot is being taken; every other console error,
// and every refusal beyond the quota, stays the page's own and fails page_health.
export const SHOT_STYLE = /^Refused to apply a stylesheet because its hash, its nonce, or 'unsafe-inline' does not appear in the style-src directive/;

export function screenshotRefusals(engine) {
  let quota = 0;
  let setAside = 0;
  return {
    // a screenshot starts: it may account for one refusal per frame on the page (WebKit only)
    begin(frames) { quota = engine === 'webkit' ? Math.max(1, Number(frames) || 1) : 0; },
    end() { quota = 0; },
    // true when this console error is the screenshot's own (and is set aside); false when it is the page's
    take(text) {
      if (quota > 0 && SHOT_STYLE.test(String(text))) {
        quota -= 1;
        setAside += 1;
        return true;
      }
      return false;
    },
    get setAside() { return setAside; },
  };
}
