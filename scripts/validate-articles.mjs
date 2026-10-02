// 記事メタ情報をZenn公式validatorへ渡す。収集・分類・公開判断は行わない。
import { readdir, readFile } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseDocument } from 'yaml';
import zennModel from 'zenn-model';

const { validateArticle } = zennModel;

export function validateArticleText(text, filename) {
  try {
    const match = text.replace(/^\uFEFF/, '').match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
    if (!match) throw new Error('先頭にYAML frontmatterが必要です。');
    const document = parseDocument(match[1], { uniqueKeys: true });
    if (document.errors.length) throw new Error(document.errors.map(e => e.message).join('; '));
    const metadata = document.toJS({ maxAliasCount: 100 });
    if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object') {
      throw new Error('frontmatterはキーと値からなるobjectで指定してください。');
    }
    if (metadata.published_at != null && typeof metadata.published_at !== 'string') {
      throw new Error('published_atは日付文字列で指定してください。');
    }
    // ファイル名を正本とし、frontmatterによるslugの置換を認めない。
    return validateArticle({ ...metadata, slug: basename(filename, '.md') });
  } catch (error) {
    return [{ type: 'frontmatter', isCritical: true, message: error.message }];
  }
}

export async function validateArticles(root) {
  const directory = join(root, 'articles');
  const files = await readdir(directory, { withFileTypes: true });
  const results = [];
  for (const file of files.sort((a, b) => a.name.localeCompare(b.name))) {
    if (file.name.startsWith('.')) continue;
    if (!file.isFile() || !file.name.endsWith('.md')) {
      results.push({ file: file.name, errors: [{ isCritical: true, message: 'articles直下には.md記事を配置してください。' }] });
      continue;
    }
    results.push({ file: file.name, errors: validateArticleText(await readFile(join(directory, file.name), 'utf8'), file.name) });
  }
  return results;
}

async function main() {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const results = await validateArticles(root);
  let critical = 0;
  for (const result of results) {
    for (const error of result.errors) {
      if (error.isCritical) critical++;
      console.error(`${error.isCritical ? 'エラー' : '注意'}: articles/${result.file}: ${error.message}`);
    }
  }
  console.log(`記事メタ情報検証: ${results.length}件、エラー${critical}件`);
  if (!results.length) console.log('記事は未作成です。配信対象の本文はありません。');
  console.log('本文・表示・本の検証とZenn同期結果はこの検査の対象外です。');
  process.exitCode = critical ? 1 : 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(`検証失敗: ${error.message}`); process.exitCode = 1; });
}
