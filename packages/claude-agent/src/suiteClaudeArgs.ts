// The Claude suite script's flags, parsed apart from the script so they can be
// tested without playing a Run.

/** Seeds as the `--seeds` flag writes them: a range when they are consecutive
 * (`1-5`), otherwise a comma list (`1,3,8`). */
export function formatSeeds(seeds: readonly number[]): string {
  const first = seeds[0];
  const last = seeds.at(-1);
  if (first === undefined || last === undefined) return "";
  const consecutive = seeds.every((seed, index) => seed === first + index);
  return consecutive && seeds.length > 1 ? `${first}-${last}` : seeds.join(",");
}
