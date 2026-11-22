// Follow the rendered links, copy in Chrome, and run the actual reader code.
const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright-core");

const [sitePath, runtimesFile, receiptFile, chrome] = process.argv.slice(2);
const site = path.resolve(sitePath);
const data = path.join(__dirname, "../_data");
const read = file => JSON.parse(fs.readFileSync(file, "utf8"));
const hash = raw => createHash("sha256").update(raw).digest("hex");
const files = read(path.join(site, "_meta/files.json")).files;
const build = read(path.join(site, "_meta/build.json"));
const current = build.product_version;
const versions = Object.keys(build.exact_versions || { [current]: true });
const runtimes = read(runtimesFile);
const entries = new Map(read(path.join(data, "coverage.json")).entries.map(item => [item.path, item]));
const examples = new Map(read(path.join(data, "examples.json")).examples.map(item => [item.id, item]));
const plan = read(path.join(data, "reader-targets.json"));
const warning = "rstimes.errors.DependencyWarning";
const expr = "polars.Expr.pldt.as_unit";
const series = "polars.Series.pldt.as_unit";
const scatter = "rstimes.Pldt.scatter";
const ctime = "rstimes.Pydt.ctime";
const desktop = Object.keys(plan).filter(entry => entry !== warning);
const mobile = [scatter, expr, ctime];
const outputs = {
  [warning]: "DependencyWarning True",
  [scatter]: "[9, None, 3]\n[1, None, 3]",
  [ctime]: "Fri Feb  9 09:30:00 2024",
  [expr]: "[-2, None]\n[-2, None]",
  [series]: "[-2, None]",
  "rstimes.Pldt.diff": "[None, 1001, None]",
};
const assertions = {
  [expr]: [
    "assert frame.select(converted).schema['event'] == pl.Datetime('us', 'UTC')",
    "assert frame.lazy().select(converted).collect().schema['event'] == pl.Datetime('us', 'UTC')",
  ],
  [scatter]: [
    "assert original.to_physical().to_list() == [1, None, 3]",
    "assert edited.to_physical().to_list() == [9, None, 3]",
  ],
};
const types = {
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};
const report = {
  started: new Date().toISOString(), source: build.documentation_commit, workflow: build.workflow_url,
  manifest_sha256: hash(fs.readFileSync(path.join(site, "_meta/files.json"))),
  readers: [], negative_controls: {}, page_errors: [],
};

function serve() {
  return http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    if (!pathname.startsWith("/rsTimes/")) {
      response.writeHead(404).end();
      return;
    }
    const relative = pathname.slice("/rsTimes/".length);
    const file = path.resolve(site, relative.endsWith("/") || !relative ? relative + "index.html" : relative);
    if (!file.startsWith(site + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
      response.writeHead(404, { "Content-Type": types[".html"] });
      response.end(fs.readFileSync(path.join(site, "404.html")));
      return;
    }
    response.writeHead(200, { "Content-Type": types[path.extname(file)] || "application/octet-stream" });
    fs.createReadStream(file).pipe(response);
  });
}

function run(runtime, code, cwd, label) {
  const result = spawnSync(runtime.python, ["-I", "-B", "-c", code], {
    cwd, encoding: "utf8", timeout: 30000,
  });
  assert.equal(result.status, 0, label + " " + (result.stderr || result.error || ""));
  assert.equal(result.stderr, "", label);
  return result.stdout.trimEnd();
}

function runtimeIdentity(runtime, version, cwd, core) {
  const result = run(runtime, [
    "import importlib.metadata as md, importlib.util as util, hashlib, json, sys",
    "from pathlib import Path",
    "import rstimes",
    "from rstimes import _native",
    "package = Path(rstimes.__file__).resolve()",
    "native = Path(_native.__file__).resolve()",
    "assert package.is_relative_to(Path(sys.prefix).resolve()) and native.is_relative_to(package.parent)",
    "print(json.dumps(dict(version=md.version('rstimes'), python=sys.version, module=str(package),",
    "  native=hashlib.file_digest(native.open('rb'), 'sha256').hexdigest(),",
    "  dependencies={name: md.version(name) for name in ('numpy', 'pandas', 'polars') if util.find_spec(name)})))",
  ].join("\n"), cwd, version + " wheel import");
  const loaded = JSON.parse(result);
  assert.equal(loaded.version, version);
  assert.equal(loaded.native, runtime.native_sha256);
  assert.equal(hash(fs.readFileSync(runtime.wheel)), runtime.wheel_sha256);
  if (core) {
    assert.equal(loaded.dependencies.pandas, undefined);
    assert.equal(loaded.dependencies.polars, undefined);
  } else {
    assert.ok(loaded.dependencies.polars, "A Polars route must use a real Polars installation");
  }
  return { ...runtime, ...loaded };
}

async function click(page, locator, destination) {
  if (page.url() === destination) {
    await locator.click();
  } else {
    await Promise.all([page.waitForURL(destination), locator.click()]);
  }
}

async function pageReceipt(page) {
  const url = new URL(page.url());
  const relative = url.pathname.slice("/rsTimes/".length);
  const file = relative.endsWith("/") ? relative + "index.html" : relative;
  const response = await page.context().request.get(url.href.split("#")[0]);
  assert.equal(response.status(), 200);
  const sha256 = hash(await response.body());
  assert.equal(sha256, files[file], file);
  return { url: url.href, file, sha256 };
}

async function reader(page, exact, entry, runtime, cwd) {
  const row = entries.get(entry);
  const id = plan[entry];
  const example = examples.get(id);
  assert.ok(example.covers.includes(entry));
  const leaf = row.page + ".html";
  const api = exact(leaf + "#" + row.anchor);
  const landing = exact(example.page.replace(/\.[^.]+$/, ".html") + "#" + id);
  const anchor = page.locator('main [id="' + row.anchor + '"]');
  let region;
  let source;
  if (entry === ctime || entry === warning) {
    const section = leaf.split("/").pop();
    await page.goto(exact("api/index.html"));
    await click(page, page.locator('main a[href="' + section + '"]').first(), exact(leaf));
    region = anchor.locator("xpath=ancestor::tr[1]");
    await region.scrollIntoViewIfNeeded();
    source = "API contents to the reference table row";
  } else {
    await page.goto(exact("genindex.html"));
    await click(page, page.locator('main a[href="' + leaf + "#" + row.anchor + '"]').first(), api);
    region = anchor.locator("xpath=parent::dl/dd");
    source = "General index to the exact signature";
  }
  const links = await region.locator("a.reference.internal").evaluateAll(nodes => nodes.map(
    link => ({ url: link.href, href: link.getAttribute("href"), text: link.innerText }),
  ));
  const link = links.find(item => item.url === landing);
  assert.ok(link, "Reader target mismatch for " + entry + ": " + JSON.stringify(links));
  const before = await pageReceipt(page);
  await click(page, region.getByRole("link", { name: link.text, exact: true }), landing);
  const after = await pageReceipt(page);
  const block = page.locator('[id="' + id + '"].highlight-python');
  const { code, expected } = await block.evaluate(el => ({
    code: el.querySelector("pre").textContent.trimEnd(),
    expected: el.nextElementSibling?.textContent.trim() === "Output"
      ? el.nextElementSibling.nextElementSibling.querySelector("pre").textContent.trimEnd()
      : null,
  }));
  const copy = block.locator("button.copybtn");
  assert.equal(await copy.getAttribute("aria-label"), "Copy code");
  await copy.click();
  const clipboard = (await page.evaluate(() => navigator.clipboard.readText())).trimEnd();
  assert.equal(clipboard, code);
  assert.notEqual(expected, null);
  if (entry in outputs) assert.equal(expected, outputs[entry]);
  const controls = assertions[entry] || [];
  const stdout = run(runtime, [clipboard, ...controls].join("\n"), cwd, entry);
  assert.equal(stdout, expected);
  return { entry, case: id, viewport: page.viewportSize(), source, before, after, link,
           clipboard, clipboard_sha256: hash(clipboard), stdout, controls };
}

async function withPage(browser, base, width, use) {
  const context = await browser.newContext({
    viewport: { width, height: width === 390 ? 844 : 900 },
    permissions: ["clipboard-read", "clipboard-write"],
  });
  try {
    await context.route("**/*", route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(12000);
    page.on("pageerror", error => report.page_errors.push(error.message));
    return await use(page);
  } finally {
    await context.close();
  }
}

async function rejectWrongLink(browser, base, exact, attempted, wrong, runtime, cwd) {
  const origin = new URL(attempted.before.url);
  const destination = new URL(wrong.after.url);
  const wrongLink = path.posix.relative(path.posix.dirname(origin.pathname), destination.pathname) + destination.hash;
  const html = fs.readFileSync(path.join(site, attempted.before.file), "utf8");
  const swapped = html.replaceAll('href="' + attempted.link.href + '"', 'href="' + wrongLink + '"');
  assert.notEqual(swapped, html, "The negative control must edit the rendered deep link");
  return withPage(browser, base, 1440, async page => {
    await page.route(origin.href.split("#")[0], route => route.fulfill({ contentType: types[".html"], body: swapped }));
    let observed;
    await assert.rejects(reader(page, exact, attempted.entry, runtime, cwd), error => {
      observed = error.message;
      return observed.includes("Reader target mismatch for " + attempted.entry)
        && observed.includes(destination.href);
    });
    return { expected: attempted.after.url, injected: destination.href, rejected: true, observed };
  });
}

async function main() {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "rstimes-doc-reader-"));
  const server = serve();
  let browser;
  try {
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolve);
    });
    const base = "http://127.0.0.1:" + server.address().port + "/rsTimes/";
    browser = await chromium.launch({ executablePath: chrome, headless: true });
    report.chrome = browser.version();
    report.runtimes = {};
    for (const version of versions) {
      const exact = part => new URL(version + "/" + part, base).href;
      const runtime = runtimes[version].full;
      report.runtimes[version] = { full: runtimeIdentity(runtime, version, work, false) };
      for (const width of [1440, 390]) {
        await withPage(browser, base, width, async page => {
          for (const entry of width === 1440 ? desktop : mobile) {
            report.readers.push({ version, ...await reader(page, exact, entry, runtime, work) });
          }
        });
      }
    }
    const exact = part => new URL(current + "/" + part, base).href;
    const core = runtimes[current].core;
    report.runtimes[current].core = runtimeIdentity(core, current, work, true);
    report.warning = await withPage(browser, base, 1440, page => reader(page, exact, warning, core, work));
    const wide = report.readers.filter(item => item.version === current && item.viewport.width === 1440);
    const a = wide.find(item => item.entry === expr);
    const b = wide.find(item => item.entry === series);
    report.negative_controls.expr_to_series = await rejectWrongLink(browser, base, exact, a, b, runtimes[current].full, work);
    report.negative_controls.series_to_expr = await rejectWrongLink(browser, base, exact, b, a, runtimes[current].full, work);
    const otherCoreURL = exact("api/errors.html#ref-parse-field-error");
    const otherCoreOutput = await withPage(browser, base, 1440, async page => {
      await page.goto(otherCoreURL);
      const code = await page.locator('[id="ref-parse-field-error"] pre').textContent();
      return run(core, code, work, "Independent wrong-link runnable control");
    });
    assert.equal(otherCoreOutput, "ParseError");
    report.negative_controls.warning_wrong_example = {
      ...await rejectWrongLink(browser, base, exact, report.warning, { after: { url: otherCoreURL } }, core, work),
      wrong_example_output: otherCoreOutput,
    };
    assert.deepEqual(report.page_errors, []);
    report.status = "pass";
    console.log(report.readers.length + " exact-version reader routes and the core warning route passed");
  } catch (error) {
    report.status = "fail";
    report.error = error.stack;
    throw error;
  } finally {
    fs.writeFileSync(receiptFile, JSON.stringify(report, null, 2) + "\n");
    if (browser) await browser.close();
    if (server.listening) await new Promise(resolve => server.close(resolve));
    fs.rmSync(work, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
