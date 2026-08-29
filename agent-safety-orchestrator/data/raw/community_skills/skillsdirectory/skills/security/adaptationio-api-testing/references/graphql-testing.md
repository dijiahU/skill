# Advanced GraphQL Testing

## Query Patterns

### Fragments

```typescript
const USER_FRAGMENT = `
  fragment UserFields on User {
    id
    name
    email
    role
  }
`;

test('query with fragments', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        ${USER_FRAGMENT}
        query GetUsers {
          users {
            ...UserFields
            posts {
              id
              title
            }
          }
        }
      `,
    },
  });

  const { data } = await response.json();
  expect(data.users[0]).toHaveProperty('email');
});
```

### Aliases

```typescript
test('multiple queries with aliases', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        query {
          firstUser: user(id: "1") { name }
          secondUser: user(id: "2") { name }
          admins: users(role: ADMIN) { name }
          regularUsers: users(role: USER) { name }
        }
      `,
    },
  });

  const { data } = await response.json();
  expect(data.firstUser.name).toBeDefined();
  expect(data.admins).toBeInstanceOf(Array);
});
```

### Pagination

```typescript
test('cursor-based pagination', async ({ request }) => {
  // First page
  const page1 = await request.post('/graphql', {
    data: {
      query: `
        query GetUsers($first: Int!, $after: String) {
          users(first: $first, after: $after) {
            edges {
              node { id name }
              cursor
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
      `,
      variables: { first: 10 },
    },
  });

  const { data: data1 } = await page1.json();
  expect(data1.users.edges).toHaveLength(10);

  // Second page
  const page2 = await request.post('/graphql', {
    data: {
      query: `...same query...`,
      variables: {
        first: 10,
        after: data1.users.pageInfo.endCursor,
      },
    },
  });

  const { data: data2 } = await page2.json();
  expect(data2.users.edges[0].node.id).not.toBe(data1.users.edges[0].node.id);
});
```

## Mutation Patterns

### Optimistic Updates

```typescript
test('mutation returns updated entity', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        mutation UpdateUser($id: ID!, $input: UpdateUserInput!) {
          updateUser(id: $id, input: $input) {
            id
            name
            updatedAt
          }
        }
      `,
      variables: {
        id: '123',
        input: { name: 'New Name' },
      },
    },
  });

  const { data } = await response.json();
  expect(data.updateUser.name).toBe('New Name');
  expect(data.updateUser.updatedAt).toBeDefined();
});
```

### Batch Mutations

```typescript
test('batch delete', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        mutation DeleteUsers($ids: [ID!]!) {
          deleteUsers(ids: $ids) {
            success
            deletedCount
            deletedIds
          }
        }
      `,
      variables: {
        ids: ['1', '2', '3'],
      },
    },
  });

  const { data } = await response.json();
  expect(data.deleteUsers.deletedCount).toBe(3);
});
```

## Subscription Testing

```typescript
import WebSocket from 'ws';

test('subscription receives updates', async ({ request }) => {
  // Connect to WebSocket
  const ws = new WebSocket('ws://localhost:4000/graphql');

  const messages: any[] = [];

  ws.on('open', () => {
    // Subscribe
    ws.send(JSON.stringify({
      type: 'subscribe',
      payload: {
        query: `
          subscription OnMessageCreated {
            messageCreated {
              id
              content
              author { name }
            }
          }
        `,
      },
    }));
  });

  ws.on('message', (data) => {
    messages.push(JSON.parse(data.toString()));
  });

  // Wait for connection
  await new Promise(r => setTimeout(r, 1000));

  // Trigger mutation
  await request.post('/graphql', {
    data: {
      query: `
        mutation {
          createMessage(content: "Hello!") { id }
        }
      `,
    },
  });

  // Wait for subscription message
  await new Promise(r => setTimeout(r, 500));

  ws.close();

  expect(messages).toContainEqual(
    expect.objectContaining({
      type: 'data',
      payload: expect.objectContaining({
        data: expect.objectContaining({
          messageCreated: expect.objectContaining({
            content: 'Hello!',
          }),
        }),
      }),
    })
  );
});
```

## Error Handling

### Validation Errors

```typescript
test('handles validation errors', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        mutation CreateUser($input: CreateUserInput!) {
          createUser(input: $input) { id }
        }
      `,
      variables: {
        input: {
          email: 'invalid-email',  // Invalid format
          name: '',  // Required field empty
        },
      },
    },
  });

  const { errors } = await response.json();
  expect(errors).toBeDefined();
  expect(errors[0].extensions.code).toBe('BAD_USER_INPUT');
});
```

### Authentication Errors

```typescript
test('handles auth errors', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        query {
          me { id email }
        }
      `,
    },
    // No auth header
  });

  const { errors } = await response.json();
  expect(errors[0].extensions.code).toBe('UNAUTHENTICATED');
});
```

### Partial Responses

```typescript
test('handles partial failures', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        query {
          user(id: "1") { name }
          nonExistentUser: user(id: "99999") { name }
        }
      `,
    },
  });

  const { data, errors } = await response.json();

  // First query succeeds
  expect(data.user.name).toBeDefined();

  // Second query has error
  expect(data.nonExistentUser).toBeNull();
  expect(errors).toContainEqual(
    expect.objectContaining({
      path: ['nonExistentUser'],
    })
  );
});
```

## Introspection

```typescript
test('schema introspection', async ({ request }) => {
  const response = await request.post('/graphql', {
    data: {
      query: `
        query {
          __schema {
            types {
              name
              kind
            }
            queryType { name }
            mutationType { name }
          }
        }
      `,
    },
  });

  const { data } = await response.json();
  expect(data.__schema.queryType.name).toBe('Query');

  const typeNames = data.__schema.types.map(t => t.name);
  expect(typeNames).toContain('User');
  expect(typeNames).toContain('Post');
});
```

## Performance Testing

```typescript
test('query complexity limit', async ({ request }) => {
  // Deeply nested query should be rejected
  const response = await request.post('/graphql', {
    data: {
      query: `
        query DeeplyNested {
          users {
            posts {
              comments {
                author {
                  posts {
                    comments {
                      author { name }
                    }
                  }
                }
              }
            }
          }
        }
      `,
    },
  });

  const { errors } = await response.json();
  expect(errors[0].message).toMatch(/complexity|depth/i);
});
```
