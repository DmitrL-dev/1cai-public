import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {T, R, P, follow} from '../build-explorer-scene.mjs';
import {TURN} from '../reference/kit/turn.mjs';
import * as TA from '../reference/kit/turn-audit.mjs';

// Supplemental coverage, not a replacement for the full orbit audit.
// Its depth oracle uses the official full-resolution 0.25 sampling unchanged.
const model = JSON.parse(readFileSync('explorer-scene.json', 'utf8'));
const states = [];
for (const pitch of [-85, -65, -45, 0, 45, 65, 85]) {
  for (let yaw = 0; yaw < 360; yaw += 30) {
    for (const profile of ['assembled', 'exploded', 'independent']) {
      const values = follow({world: {
        R: TURN.compose(TURN.rotation([1, 0, 0], pitch), TURN.rotation([0, 0, 1], yaw)),
        t: [0, 0, 0],
      }, apart: profile === 'exploded' ? 1 : 0});
      if (profile === 'independent') {
        for (const [i, object] of model.objects.entries()) {
          // Different, deterministic intermediate/end-point slides for every system.
          values[object.group] = ((i + yaw / 30 + (pitch + 85)) % 5) / 4 * object.travel;
        }
      }
      states.push({pitch, yaw, profile, values});
    }
  }
}
const result = TA.orbit(T, R, P, {
  only: ['depth'],
  quick: false,
  depthAngles: states.length,
  sweep: {at: index => states[Math.min(states.length - 1, Math.floor(index))].values,
    from: 0, to: states.length, frame: 1},
  log: message => console.log(message),
});
const report = {
  scope: 'Supplemental full-resolution official depth oracle. Finite grid: 12 yaw angles × 7 pitches × 3 slide profiles. Not a continuous proof, not a full audit, and not browser QA.',
  sourceSha256: Object.fromEntries(['build-explorer-scene.mjs', 'reference/kit/turn-build.mjs', 'reference/kit/turn.mjs', 'reference/kit/turn-audit.mjs'].map(path => [path, createHash('sha256').update(readFileSync(path)).digest('hex')])),
  contract: model.interaction,
  parts: model.parts.length,
  systems: model.objects.length,
  states: states.map(({values, ...description}) => description),
  failures: TA.orbitFailures(result),
  result,
};
writeFileSync('qa/explorer-mixed-depth.json', JSON.stringify(report, null, 2));
console.log(TA.orbitReport(result));
console.log(`MIXED_DEPTH_EXIT=${report.failures ? 1 : 0}`);
process.exitCode = report.failures ? 1 : 0;
