<stack>
  Bun runtime, Hono web framework, Zod validation.
</stack>

<structure>
  src/index.ts     — App entry, middleware, route mounting
  src/routes/      — Route modules (create as needed)
</structure>

<routes>
  Create routes in src/routes/ and mount them in src/index.ts.

  Example route file (src/routes/todos.ts):
  ```typescript
  import { Hono } from "hono";
  import { zValidator } from "@hono/zod-validator";
  import { z } from "zod";

  const todosRouter = new Hono();

  todosRouter.get("/", (c) => {
    return c.json({ todos: [] });
  });

  todosRouter.post(
    "/",
    zValidator("json", z.object({ title: z.string() })),
    (c) => {
      const { title } = c.req.valid("json");
      return c.json({ todo: { id: "1", title } });
    }
  );

  export { todosRouter };
  ```

  Mount in src/index.ts:
  ```typescript
  import { todosRouter } from "./routes/todos";
  app.route("/api/todos", todosRouter);
  ```

  IMPORTANT: Make sure all endpoints and routes are prefixed with `/api/`
</routes>

<database>
  No database is configured by default.
  If the user needs to persist data or have user accounts, use the database-auth skill and then update this file to reflect the changes.
</database>

<package_management>
  CRITICAL: After using `bun add` to install any package, you MUST immediately commit the updated package.json:

  ```bash
  bun add some-package
  git add package.json bun.lock
  git commit -m "chore: add some-package dependency"
  ```

  Why: If package.json is not committed, the package will be lost when the sandbox restarts,
  causing "Cannot find package" errors on the next session.
</package_management>