import { describe, expect, it } from "vitest";

import { API_BASE_URL } from "./client";

describe("API client configuration", () => {
  it("uses a configurable backend base URL", () => {
    expect(API_BASE_URL).toBeTruthy();
  });
});
