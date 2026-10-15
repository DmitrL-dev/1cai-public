'use strict';
// Return from activation before running/closing the owned window. Awaiting quit
// inside extension activation can make shutdown wait for its own activation.
function start(run, quit) {
  void Promise.resolve().then(run).catch(() => undefined).then(quit).catch(() => undefined);
}
module.exports = {start};
