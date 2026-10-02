import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { validateArticles, validateArticleText } from '../scripts/validate-articles.mjs';

const article = `---
title: "実験記事"
emoji: "🔬"
type: "tech"
topics: ["opensource"]
published: false
---
観測記録。
`;
const critical = errors => errors.some(e => e.isCritical);

test('下書き・公開記事・CRLFとBOMのメタ情報を扱える', () => {
  assert.equal(critical(validateArticleText(article, 'example-article-001.md')), false);
  assert.equal(critical(validateArticleText(article.replace('false', 'true'), 'example-article-001.md')), false);
  assert.equal(critical(validateArticleText('\uFEFF' + article.replaceAll('\n', '\r\n'), 'example-article-001.md')), false);
});

test('壊れたYAML・重複キー・文字列の公開設定を通さない', () => {
  for (const text of [article.replace('false', '"false"'), article.replace('topics: ["opensource"]', 'topics: ['), article.replace('published: false', 'published: false\npublished: true'), '本文のみ']) {
    assert.equal(critical(validateArticleText(text, 'example-article-001.md')), true);
  }
});

test('ファイル名のslugとZenn公式のトピック上限を検査する', () => {
  assert.equal(critical(validateArticleText(article, 'short.md')), true);
  assert.equal(critical(validateArticleText(article.replace('title: "実験記事"', 'slug: example-article-001\ntitle: "実験記事"'), 'short.md')), true);
  assert.equal(critical(validateArticleText(article.replace('["opensource"]', '["a", "b", "c", "d", "e", "f"]'), 'example-article-001.md')), true);
});

test('articles以外のvendor資料を読まず、空の初期構成も扱える', async () => {
  const root = await mkdtemp(join(tmpdir(), 'zennobserver-test-'));
  try {
    await mkdir(join(root, 'articles'));
    await mkdir(join(root, '.vendor'));
    await writeFile(join(root, '.vendor', 'unrelated.md'), '壊れた資料');
    assert.deepEqual(await validateArticles(root), []);
    await writeFile(join(root, 'articles', 'example-article-001.md'), article);
    const results = await validateArticles(root);
    assert.equal(results.length, 1);
    assert.equal(critical(results[0].errors), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
