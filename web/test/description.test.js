import {test} from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../src/description.js',import.meta.url),'utf8').replace('export function','function');
function render(text){const dom=new JSDOM('',{runScripts:'outside-only'});const result=dom.window.eval(`${source};descriptionHTML(${JSON.stringify(text)})`);const root=dom.window.document.createElement('div');root.innerHTML=result;return {dom,root};}
test('encoded feed HTML retains paragraphs, headings and readable bullets',()=>{const {dom,root}=render('&amp;lt;h4&amp;gt;Responsibilities&amp;lt;/h4&amp;gt;&amp;lt;p&amp;gt;Support our users.&amp;lt;/p&amp;gt;&amp;lt;ul&amp;gt;&amp;lt;li&amp;gt;Resolve tickets&amp;lt;/li&amp;gt;&amp;lt;/ul&amp;gt;');assert.equal(root.querySelector('h3').textContent,'Responsibilities');assert.equal(root.querySelector('li').textContent,'Resolve tickets');assert.equal(root.querySelector('p').textContent,'Support our users.');dom.window.close();});
test('untrusted source markup cannot add scripts, attributes or external resources',()=>{const {dom,root}=render('<p onclick="alert(1)">Role</p><script>alert(1)</script><img src="https://example.com/track"><a href="javascript:alert(1)">Apply</a><svg onload="alert(1)"></svg>');assert.equal(root.querySelectorAll('script,img,svg,a,[onclick],[onload]').length,0);assert.match(root.textContent,/RoleApply/);dom.window.close();});
