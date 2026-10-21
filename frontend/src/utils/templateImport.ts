import { createAttackTemplate } from '../api';

export type TemplateImportDraft = {
  name: string;
  template_text: string;
  variables: string[];
  version: string;
  status: string;
};

export type TemplateImportSummary = {
  imported: number;
  errors: string[];
};

export const TEMPLATE_IMPORT_ACCEPT = '.json,.jsonl,.ndjson,.txt';
const TEMPLATE_IMPORT_LIMIT = 500;

export function getErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (
      error as { response?: { data?: { detail?: unknown } } }
    ).response;
    if (typeof response?.data?.detail === 'string') return response.data.detail;
  }
  return error instanceof Error ? error.message : '未知错误';
}

function detectVariables(templateText: string): string[] {
  const names = new Set<string>();
  const pattern =
    /\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}/g;
  for (const match of templateText.matchAll(pattern)) {
    const name = match[1] ?? match[2];
    if (!name) continue;
    names.add(['seed', 'behavior'].includes(name) ? 'prompt' : name);
  }
  if (/\{\s*0\s*\}/.test(templateText)) names.add('prompt');
  return Array.from(names);
}

function normalizeVariables(value: unknown, templateText: string): string[] {
  const detected = detectVariables(templateText);
  if (Array.isArray(value)) {
    return Array.from(
      new Set([
        ...value
          .map((item) => String(item).trim())
          .filter(Boolean)
          .map((item) =>
            ['0', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  if (typeof value === 'string') {
    return Array.from(
      new Set([
        ...value
          .split(/[,;，；\s]+/)
          .map((item) => item.trim())
          .filter(Boolean)
          .map((item) =>
            ['0', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  return detected;
}

function draftFromRecord(
  record: unknown,
  baseName: string,
  index: number,
): TemplateImportDraft {
  if (typeof record === 'string') {
    const templateText = record.trim();
    if (!templateText) throw new Error('模板内容为空');
    return {
      name: `${baseName}-${index}`,
      template_text: templateText,
      variables: detectVariables(templateText),
      version: 'v1',
      status: 'active',
    };
  }

  if (typeof record !== 'object' || record === null || Array.isArray(record)) {
    throw new Error('模板记录必须是对象或字符串');
  }

  const row = record as Record<string, unknown>;
  const templateText = row.template_text ?? row.template ?? row.text ?? row.prompt;
  if (typeof templateText !== 'string' || !templateText.trim()) {
    throw new Error('缺少 template_text 字段');
  }

  return {
    name: String(row.name ?? `${baseName}-${index}`).trim(),
    template_text: templateText.trim(),
    variables: normalizeVariables(row.variables, templateText),
    version: String(row.version ?? 'v1').trim() || 'v1',
    status: ['active', 'draft', 'disabled'].includes(String(row.status))
      ? String(row.status)
      : 'active',
  };
}

async function parseTemplateFile(file: File): Promise<TemplateImportDraft[]> {
  const content = await file.text();
  const suffix = file.name.split('.').pop()?.toLowerCase() ?? '';
  const baseName = file.name.replace(/\.[^.]+$/, '');
  let records: unknown[];

  if (suffix === 'json') {
    const payload: unknown = JSON.parse(content);
    if (Array.isArray(payload)) {
      records = payload;
    } else if (typeof payload === 'object' && payload !== null) {
      const object = payload as Record<string, unknown>;
      const nested = object.items ?? object.templates ?? object.data;
      records = Array.isArray(nested) ? nested : [payload];
    } else {
      records = [payload];
    }
  } else if (suffix === 'jsonl' || suffix === 'ndjson') {
    records = content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line) as unknown;
        } catch {
          return line;
        }
      });
  } else if (suffix === 'txt') {
    records = content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  } else {
    throw new Error('只支持 JSON、JSONL、NDJSON、TXT 文件');
  }

  if (!records.length) throw new Error('文件中没有模板');
  if (records.length > TEMPLATE_IMPORT_LIMIT) {
    throw new Error(`单个文件最多导入 ${TEMPLATE_IMPORT_LIMIT} 条模板`);
  }

  return records.map((record, index) =>
    draftFromRecord(record, baseName, index + 1),
  );
}

export async function importTemplateFiles(
  files: File[],
): Promise<TemplateImportSummary> {
  if (!files.length) throw new Error('请选择模板文件');
  const drafts = (await Promise.all(files.map(parseTemplateFile))).flat();
  if (!drafts.length) throw new Error('没有可导入的模板');

  const errors: string[] = [];
  let imported = 0;
  for (const draft of drafts) {
    try {
      await createAttackTemplate({ ...draft, method_code: 'custom' });
      imported += 1;
    } catch (error) {
      errors.push(`${draft.name}: ${getErrorMessage(error)}`);
    }
  }
  return { imported, errors };
}
