export const coverOptions = [2, 3, 4, 5, 7];

export function coverDays(selected) {
  if (!Array.isArray(selected) || selected.some((value) => !coverOptions.includes(value))) {
    throw new TypeError("Cover selections must be supported policy days.");
  }
  const unique = [...new Set(selected)];
  return unique.length === 1 ? unique[0] : 3;
}

export function supportedGrain(scope) {
  const scopes = {
    company: { sales: true, production: true, cash: true },
    product: { sales: true, production: true, cash: false },
    slice: { sales: true, production: false, cash: false },
  };
  if (!Object.hasOwn(scopes, scope)) throw new TypeError("Unknown analytical grain.");
  return scopes[scope];
}

export function assessClaim(claim) {
  const claims = {
    A: { correct: true, message: "Supported. Product, territory, month and denominator all match the sales query." },
    B: { correct: false, message: "That cash balance belongs to the whole company. The data provides no campaign allocation. Try another sentence." },
    C: { correct: false, message: "Correlation describes an association. It cannot establish what changing production would cause. Try another sentence." },
  };
  if (!Object.hasOwn(claims, claim)) throw new TypeError("Unknown briefing claim.");
  return claims[claim];
}
