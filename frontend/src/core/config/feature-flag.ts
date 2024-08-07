/* Copyright 2024 Marimo. All rights reserved. */

import { repl } from "@/utils/repl";
import type { UserConfig } from "vite";
import { saveUserConfig } from "../network/requests";
import { getUserConfig } from "./config";

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface ExperimentalFeatures {
  markdown: boolean;
  wasm_layouts: boolean;
  // Add new feature flags here
}

const defaultValues: ExperimentalFeatures = {
  markdown: true,
  wasm_layouts: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T,
): ExperimentalFeatures[T] {
  return (
    (getUserConfig().experimental?.[feature] as ExperimentalFeatures[T]) ??
    defaultValues[feature]
  );
}

function setFeatureFlag(
  feature: keyof UserConfig["experimental"],
  value: boolean,
) {
  const userConfig = getUserConfig();
  userConfig.experimental[feature] = value;
  saveUserConfig({ config: userConfig });
}

// Allow setting feature flags from the console
repl(setFeatureFlag, "setFeatureFlag");
