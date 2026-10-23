#
# Pebble build rules, plus the debug switches below.
#
import os.path

top = '.'
out = 'build'


def options(ctx):
    ctx.load('pebble_sdk')


def configure(ctx):
    ctx.load('pebble_sdk')


def debug_defines():
    """Debug-only switches, read from the environment so a release build never
    carries them. See README.md.

      SKEL_SHOW_TIME=1008   start the clock at 10:08 (store shots)
      SKEL_FAST=n           a "minute" lasts n seconds (film rollovers quickly)
      SKEL_DEBUG=1          frame time and free heap on screen
    """
    defines = []
    for flag in ('SKEL_SHOW_TIME', 'SKEL_FAST', 'SKEL_DEBUG'):
        value = os.environ.get(flag)
        if value:
            defines.append('%s=%d' % (flag, int(value)))
    return defines


def build(ctx):
    ctx.load('pebble_sdk')

    binaries = []
    cached_env = ctx.env
    for platform in ctx.env.TARGET_PLATFORMS:
        ctx.env = ctx.all_envs[platform]
        ctx.env.append_value('DEFINES', debug_defines())
        ctx.set_group(ctx.env.PLATFORM_NAME)
        app_elf = '{}/pebble-app.elf'.format(ctx.env.BUILD_DIR)
        ctx.pbl_build(source=ctx.path.ant_glob('src/c/**/*.c'), target=app_elf, bin_type='app')
        binaries.append({'platform': platform, 'app_elf': app_elf})
    ctx.env = cached_env

    ctx.set_group('bundle')
    ctx.pbl_bundle(binaries=binaries,
                   js=ctx.path.ant_glob(['src/pkjs/**/*.js', 'src/pkjs/**/*.json']),
                   js_entry_file='src/pkjs/index.js')
