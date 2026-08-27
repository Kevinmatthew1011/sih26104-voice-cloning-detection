/**
 * Utility formatters for SIH26104 Voice Cloning Detection Platform.
 */

/**
 * Format active detection engine and model version for the top Navbar status badge.
 * Examples:
 * - formatNavbarEngineLabel("aasist", "aasist-v1") -> "AASIST ML · aasist-v1"
 * - formatNavbarEngineLabel("baseline", "baseline-v1") -> "BASELINE ML · baseline-v1"
 * - formatNavbarEngineLabel("mock", "mock-v1") -> "MOCK ENGINE"
 */
export function formatNavbarEngineLabel(
  engine?: string | null,
  modelVersion?: string | null
): string {
  const normEngine = (engine || '').toLowerCase().trim();
  const version = modelVersion || '';

  if (normEngine === 'aasist' || version.startsWith('aasist')) {
    return `AASIST ML · ${modelVersion || 'aasist-v1'}`;
  }
  if (normEngine === 'baseline' || version.startsWith('baseline')) {
    return `BASELINE ML · ${modelVersion || 'baseline-v1'}`;
  }
  if (normEngine === 'mock' || version.startsWith('mock')) {
    return 'MOCK ENGINE';
  }
  if (normEngine) {
    return `${normEngine.toUpperCase()} · ${version || 'v1'}`;
  }
  return 'MOCK ENGINE';
}

/**
 * Format full engine / model display name for result cards, case details, and dropzone.
 * Examples:
 * - formatModelDisplayName("aasist-v1", "aasist") -> "AASIST ML Model (aasist-v1)"
 * - formatModelDisplayName("baseline-v1", "baseline") -> "Baseline ML Model (baseline-v1)"
 * - formatModelDisplayName("mock-v1", "mock") -> "Mock Detection Engine (mock-v1)"
 */
export function formatModelDisplayName(
  modelVersion?: string | null,
  engineType?: string | null
): string {
  const v = (modelVersion || '').toLowerCase().trim();
  const e = (engineType || '').toLowerCase().trim();

  if (v === 'aasist-v1' || e === 'aasist' || v.startsWith('aasist')) {
    return `AASIST ML Model (${modelVersion || 'aasist-v1'})`;
  }
  if (v === 'baseline-v1' || e === 'baseline' || v.startsWith('baseline')) {
    return `Baseline ML Model (${modelVersion || 'baseline-v1'})`;
  }
  if (v === 'mock-v1' || e === 'mock' || v.startsWith('mock')) {
    return `Mock Detection Engine (${modelVersion || 'mock-v1'})`;
  }
  return modelVersion || 'Mock Detection Engine';
}
