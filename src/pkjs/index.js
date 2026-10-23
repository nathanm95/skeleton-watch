var Clay = require('@rebble/clay');
var clayConfig = require('./config');

// Clay renders the settings page, remembers the answers on the phone and posts
// them to the watch keyed by the messageKeys in package.json.
// eslint-disable-next-line no-unused-vars
var clay = new Clay(clayConfig);
