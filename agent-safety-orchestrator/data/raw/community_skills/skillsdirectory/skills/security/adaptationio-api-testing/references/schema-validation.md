# JSON Schema Validation with Ajv

## Installation

```bash
npm install ajv ajv-formats
```

## Basic Setup

```typescript
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true });
addFormats(ajv);
```

## Common Schemas

### User Schema

```typescript
const userSchema = {
  type: 'object',
  properties: {
    id: { type: 'number' },
    name: { type: 'string', minLength: 1 },
    email: { type: 'string', format: 'email' },
    role: { enum: ['admin', 'user', 'guest'] },
    createdAt: { type: 'string', format: 'date-time' },
    profile: {
      type: 'object',
      properties: {
        avatar: { type: 'string', format: 'uri' },
        bio: { type: 'string', maxLength: 500 },
      },
    },
  },
  required: ['id', 'name', 'email'],
  additionalProperties: false,
};
```

### Paginated Response Schema

```typescript
const paginatedSchema = (itemSchema: object) => ({
  type: 'object',
  properties: {
    data: {
      type: 'array',
      items: itemSchema,
    },
    pagination: {
      type: 'object',
      properties: {
        page: { type: 'number', minimum: 1 },
        perPage: { type: 'number', minimum: 1, maximum: 100 },
        total: { type: 'number', minimum: 0 },
        totalPages: { type: 'number', minimum: 0 },
      },
      required: ['page', 'perPage', 'total', 'totalPages'],
    },
  },
  required: ['data', 'pagination'],
});
```

### Error Response Schema

```typescript
const errorSchema = {
  type: 'object',
  properties: {
    error: {
      type: 'object',
      properties: {
        code: { type: 'string' },
        message: { type: 'string' },
        details: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              field: { type: 'string' },
              message: { type: 'string' },
            },
          },
        },
      },
      required: ['code', 'message'],
    },
  },
  required: ['error'],
};
```

## Usage in Tests

### Basic Validation

```typescript
import { test, expect } from '@playwright/test';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true });
addFormats(ajv);

test('validate user response', async ({ request }) => {
  const response = await request.get('/api/users/1');
  const user = await response.json();

  const validate = ajv.compile(userSchema);
  const valid = validate(user);

  if (!valid) {
    console.log('Validation errors:', validate.errors);
  }

  expect(valid).toBe(true);
});
```

### Reusable Validation Helper

```typescript
// helpers/schema-validator.ts
import Ajv, { ValidateFunction } from 'ajv';
import addFormats from 'ajv-formats';

const ajv = new Ajv({ allErrors: true });
addFormats(ajv);

const validators = new Map<string, ValidateFunction>();

export function validateSchema(schemaName: string, schema: object, data: unknown): {
  valid: boolean;
  errors: string[];
} {
  if (!validators.has(schemaName)) {
    validators.set(schemaName, ajv.compile(schema));
  }

  const validate = validators.get(schemaName)!;
  const valid = validate(data);

  const errors = valid ? [] : validate.errors!.map(err =>
    `${err.instancePath} ${err.message}`
  );

  return { valid, errors };
}

// Usage in test
test('validate with helper', async ({ request }) => {
  const response = await request.get('/api/users/1');
  const user = await response.json();

  const { valid, errors } = validateSchema('user', userSchema, user);

  if (!valid) {
    console.log('Validation errors:', errors);
  }

  expect(valid).toBe(true);
});
```

### Custom Formats

```typescript
// Add custom format for phone numbers
ajv.addFormat('phone', /^\+?[1-9]\d{1,14}$/);

const contactSchema = {
  type: 'object',
  properties: {
    phone: { type: 'string', format: 'phone' },
  },
};
```

### Custom Keywords

```typescript
// Add custom keyword for array uniqueness by field
ajv.addKeyword({
  keyword: 'uniqueItemProperties',
  type: 'array',
  validate: function (schema: string[], data: any[]) {
    if (!Array.isArray(data)) return true;

    for (const prop of schema) {
      const values = data.map(item => item[prop]);
      if (new Set(values).size !== values.length) {
        return false;
      }
    }
    return true;
  },
});

const usersArraySchema = {
  type: 'array',
  items: userSchema,
  uniqueItemProperties: ['id', 'email'],  // IDs and emails must be unique
};
```

## Schema Registry Pattern

```typescript
// schemas/index.ts
export const schemas = {
  user: userSchema,
  post: postSchema,
  comment: commentSchema,
  paginatedUsers: paginatedSchema(userSchema),
  error: errorSchema,
};

// test-utils/validate.ts
import { schemas } from '../schemas';

export function expectValidSchema(
  schemaName: keyof typeof schemas,
  data: unknown
) {
  const validate = ajv.compile(schemas[schemaName]);
  const valid = validate(data);

  if (!valid) {
    throw new Error(
      `Schema validation failed:\n${JSON.stringify(validate.errors, null, 2)}`
    );
  }
}

// In test
test('list users returns valid response', async ({ request }) => {
  const response = await request.get('/api/users');
  const data = await response.json();

  expectValidSchema('paginatedUsers', data);
});
```

## Contract Testing

```typescript
// Compare API response against OpenAPI schema
import SwaggerParser from '@apidevtools/swagger-parser';

test('response matches OpenAPI spec', async ({ request }) => {
  const api = await SwaggerParser.dereference('./openapi.yaml');

  const response = await request.get('/api/users/1');
  const user = await response.json();

  const userSchema = api.components.schemas.User;
  const validate = ajv.compile(userSchema);

  expect(validate(user)).toBe(true);
});
```
