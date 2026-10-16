'use strict';
// Core versions admitted by this Companion build, oldest first. A new Core
// version is never admitted automatically: add it here only after the exact
// Core/Companion pair is qualified. dev18 stays reserved and refused.
const ADMITTED=Object.freeze(['0.1.0.dev4','0.1.0.dev5','0.1.0.dev6','0.1.0.dev7','0.1.0.dev8','0.1.0.dev9','0.1.0.dev10','0.1.0.dev11','0.1.0.dev12','0.1.0.dev13','0.1.0.dev14','0.1.0.dev15','0.1.0.dev16','0.1.0.dev17','0.1.0.dev19','0.1.0.dev20']);
const since=floor=>Object.freeze(ADMITTED.slice(ADMITTED.indexOf(floor)));
// Draft repair/edit needs dev7; native checks, BSL runs and tests need dev8.
module.exports=Object.freeze({PROFILE_CORE_VERSIONS:ADMITTED,REPAIR_CORE_VERSIONS:since('0.1.0.dev7'),NATIVE_CORE_VERSIONS:since('0.1.0.dev8')});
