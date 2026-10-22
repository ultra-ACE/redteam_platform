import { createAttackTemplate } from '../api';

export type TemplateImportDraft = {
  library_name: string;
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

export const TEMPLATE_IMPORT_ACCEPT = '.json,.jsonl,.ndjson,.csv,.txt';
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
    names.add(['question', 'seed', 'behavior'].includes(name) ? 'prompt' : name);
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
            ['0', 'question', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed) as unknown;
        if (Array.isArray(parsed)) {
          return normalizeVariables(parsed, templateText);
        }
      } catch {
        // Fall back to delimiter splitting.
      }
    }
    return Array.from(
      new Set([
        ...trimmed
          .split(/[,;|，；\s]+/)
          .map((item) => item.trim())
          .filter(Boolean)
          .map((item) =>
            ['0', 'question', 'seed', 'behavior'].includes(item) ? 'prompt' : item,
          ),
        ...detected,
      ]),
    );
  }
  return detected;
}

function parseCsvRows(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;

  const pushField = () => {
    row.push(field);
    field = '';
  };
  const pushRow = () => {
    pushField();
    if (row.some((value) => value.trim())) rows.push(row);
    row = [];
  };

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index];
    if (inQuotes) {
      if (char === '"' && content[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"' && field.length === 0) {
      inQuotes = true;
    } else if (char === ',') {
      pushField();
    } else if (char === '\n') {
      pushRow();
    } else if (char === '\r') {
      if (content[index + 1] === '\n') index += 1;
      pushRow();
    } else {
      field += char;
    }
  }

  if (field.length || row.length) pushRow();
  return rows;
}

const CSV_HEADER_ALIASES: Record<string, string> = {
  library_name: 'library_name',
  模板库名称: 'library_name',
  模板库: 'library_name',
  name: 'name',
  template_name: 'name',
  模板名称: 'name',
  template_text: 'template_text',
  prompt_pattern: 'template_text',
  模板内容: 'template_text',
  template: 'template_text',
  variables: 'variables',
  变量: 'variables',
  变量列表: 'variables',
  version: 'version',
  版本: 'version',
  status: 'status',
  状态: 'status',
};

function parseCsvRecords(content: string): Record<string, string>[] {
  const rows = parseCsvRows(content.replace(/^\uFEFF/, ''));
  if (rows.length < 2) throw new Error('CSV 文件至少需要表头和一行模板');

  const headers = rows[0].map((header) => {
    const normalized = header.trim().toLowerCase();
    return CSV_HEADER_ALIASES[normalized] ?? normalized;
  });
  if (!headers.includes('template_text')) {
    throw new Error('CSV 缺少 template_text（模板内容）列');
  }

  return rows.slice(1).map((values) => {
    const record: Record<string, string> = {};
    headers.forEach((header, index) => {
      if (header) record[header] = values[index] ?? '';
    });
    return record;
  });
}

async function readFileText(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer).replace(/^\uFEFF/, '');
  } catch {
    try {
      return new TextDecoder('gbk').decode(buffer).replace(/^\uFEFF/, '');
    } catch {
      return new TextDecoder().decode(buffer).replace(/^\uFEFF/, '');
    }
  }
}

function draftFromRecord(
  record: unknown,
  baseName: string,
  index: number,
  defaultLibraryName: string,
): TemplateImportDraft {
  if (typeof record === 'string') {
    const templateText = record.trim();
    if (!templateText) throw new Error('模板内容为空');
    return {
      library_name: defaultLibraryName,
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
    library_name: String(row.library_name ?? defaultLibraryName).trim() || defaultLibraryName,
    name: String(row.name ?? `${baseName}-${index}`).trim(),
    template_text: templateText.trim(),
    variables: normalizeVariables(row.variables, templateText),
    version: String(row.version ?? 'v1').trim() || 'v1',
    status: ['active', 'draft', 'disabled'].includes(String(row.status))
      ? String(row.status)
      : 'active',
  };
}

async function parseTemplateFile(
  file: File,
  defaultLibraryName: string,
): Promise<TemplateImportDraft[]> {
  const content = await readFileText(file);
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
  } else if (suffix === 'csv') {
    records = parseCsvRecords(content);
  } else {
    throw new Error('只支持 JSON、JSONL、NDJSON、CSV、TXT 文件');
  }

  if (!records.length) throw new Error('文件中没有模板');
  if (records.length > TEMPLATE_IMPORT_LIMIT) {
    throw new Error(`单个文件最多导入 ${TEMPLATE_IMPORT_LIMIT} 条模板`);
  }

  return records.map((record, index) =>
    draftFromRecord(record, baseName, index + 1, defaultLibraryName),
  );
}

export async function importTemplateFiles(
  files: File[],
  defaultLibraryName = '默认模板库',
): Promise<TemplateImportSummary> {
  if (!files.length) throw new Error('请选择模板文件');
  const libraryName = defaultLibraryName.trim() || '默认模板库';
  const drafts = (
    await Promise.all(files.map((file) => parseTemplateFile(file, libraryName)))
  ).flat();
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
