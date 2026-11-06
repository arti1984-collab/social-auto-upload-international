/** Local Markdown rendering only; stdin/stdout use JSON, so the body never travels through argv. */
import { renderMarkdownDocument, resolveMarkdownStyle } from 'baoyu-md';
import { Marked } from 'marked';
import { load } from 'cheerio';

let input = '';
// Decode by character so long non-ASCII documents do not get replacement chars at Buffer boundaries.
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) input += chunk;
try {
  const { content, theme } = JSON.parse(input);
  const markdown = new Marked({ gfm: true });
  // Diagram extensions emit SVG or remote images, so never degrade them to plain code blocks silently.
  const tokens = markdown.lexer(content);
  markdown.walkTokens(tokens, token => {
    if (token.type === 'html' && /<\/?(?:script|style|link|iframe|object|embed)\b/i.test(token.raw)) {
      throw Error('Inline HTML in Markdown must not contain scripts, external resources or stylesheets; use inline styles');
    }
    if (token.type === 'code' && /^(mermaid|plantuml|infographic)(\s|$)/i.test(token.lang || '')) {
      throw Error(`${token.lang} diagrams are not supported; export them as local images first`);
    }
  });
  if (theme === 'plain') {
    process.stdout.write(JSON.stringify({ html: markdown.parser(tokens), metadata: {} }));
  } else {
    // Pass every option explicitly so upstream cannot pick up a user EXTEND.md and change our defaults.
    const style = resolveMarkdownStyle({ theme });
    const result = await renderMarkdownDocument(content, {
      theme, primaryColor: style.primaryColor, fontFamily: style.fontFamily,
      fontSize: style.fontSize, codeTheme: 'github', countStatus: false,
      citeStatus: false, keepTitle: true, legend: 'none',
      isMacCodeBlock: false, isShowLineNumber: false, themeMode: 'light',
    });
    // Upstream keeps a hidden SVG even with Mac code decoration disabled; remove that decoration only, never user content.
    const $ = load(result.html);
    $('pre.code__pre > span.mac-sign').remove();
    // Upstream fakes lists with "1. / • " text and display:block, which double-numbers once a platform strips CSS.
    // Restore native list semantics and keep the rest of the theme so markers render once locally and after CSS filtering.
    $('ol,ul').each((_, list) => {
      const ordered = list.tagName === 'ol';
      $(list).children('li.listitem').each((index, item) => {
        const first = item.children[0];
        if (first?.type !== 'text') return;
        const prefix = first.data.match(ordered ? /^(\d+)\. / : /^• /);
        if (!prefix) return;
        if (ordered && index === 0 && Number(prefix[1]) !== 1) $(list).attr('start', prefix[1]);
        first.data = first.data.slice(prefix[0].length);
        $(item).attr('style', ($(item).attr('style') || '').replace(/display:\s*block\s*;/, 'display: list-item;'));
      });
    });
    process.stdout.write(JSON.stringify({ html: $.html(), metadata: result.meta }));
  }
} catch (error) {
  process.stderr.write(error.stack || String(error));
  process.exitCode = 1;
}
