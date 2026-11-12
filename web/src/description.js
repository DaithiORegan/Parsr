// Rebuild source markup from text and a small set of structural tags only.
// No source attributes, links, scripts or event handlers reach the live DOM.
export function descriptionHTML(value) {
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let text = String(value || '').replace(/\r\n/g, '\n');
  const decoder = document.createElement('textarea');
  for (let i=0;i<4;i++) {
    decoder.innerHTML = text;
    const decoded = decoder.value;
    if (decoded === text) break;
    text = decoded;
  }
  if (!/<\/?[a-z][^>]*>/i.test(text)) {
    return text.split(/\n\s*\n/).map(p => `<p>${escape(p.trim()).replace(/\n/g,'<br>')}</p>`).join('');
  }
  const doc = new DOMParser().parseFromString(text, 'text/html');
  const blocked = new Set(['SCRIPT','STYLE','IFRAME','OBJECT','EMBED','SVG','MATH','FORM','INPUT','BUTTON','TEMPLATE','NOSCRIPT','IMG','VIDEO','AUDIO']);
  function render(node) {
    if (node.nodeType === 3) return escape(node.textContent);
    if (node.nodeType !== 1 || blocked.has(node.tagName)) return '';
    const content = [...node.childNodes].map(render).join('');
    const name = node.tagName.toLowerCase();
    if (name === 'br') return '<br>';
    if (['h1','h2','h3','h4','h5','h6'].includes(name)) return `<h3>${content}</h3>`;
    if (['p','ul','ol','li','strong','b','em','i','blockquote'].includes(name)) return `<${name}>${content}</${name}>`;
    if (['div','section','article'].includes(name)) return `<div>${content}</div>`;
    return content;
  }
  return [...doc.body.childNodes].map(render).join('');
}
