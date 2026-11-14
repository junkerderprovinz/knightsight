// Lets smoke_wayland.py steer the headless shell through its Eval method: where windows
// are, moving them and a pointer of its own. It puts the shell in unsafe mode, which Eval
// and the screenshot service need, so it belongs in a throwaway test session only.
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const pause = (ms) => new Promise((resolve) => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve();
    return GLib.SOURCE_REMOVE;
}));

function rect(r) {
    return [r.x, r.y, r.width, r.height];
}

function find(app) {
    return global.get_window_actors().map((a) => a.meta_window)
        .find((w) => w.get_gtk_application_id() === app || w.get_wm_class() === app);
}

export default class SmokeHelper extends Extension {
    enable() {
        global.context.unsafe_mode = true;
        const seat = Clutter.get_default_backend().get_default_seat();
        const pointer = seat.create_virtual_device(Clutter.InputDeviceType.POINTER_DEVICE);
        const now = () => GLib.get_monotonic_time();

        globalThis.smoke = {
            ready: () => !Main.layoutManager._startingUp,
            hideOverview: () => {
                Main.overview.hide();
                return !Main.overview.visible;
            },
            windows: () => global.get_window_actors().map((a) => {
                const w = a.meta_window;
                return {
                    title: w.get_title(),
                    app: w.get_gtk_application_id() ?? w.get_wm_class(),
                    frame: rect(w.get_frame_rect()),
                    buffer: rect(w.get_buffer_rect()),
                    focus: w.has_focus(),
                    mapped: a.mapped,
                };
            }),
            place: (app, x, y, width, height) => {
                const w = find(app);
                if (width)
                    w.move_resize_frame(true, x, y, width, height);
                else
                    w.move_frame(true, x, y);
                return rect(w.get_frame_rect());
            },
            click: async (x, y) => {
                pointer.notify_absolute_motion(now(), x, y);
                await pause(150);
                pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.PRESSED);
                await pause(100);
                pointer.notify_button(now(), Clutter.BUTTON_PRIMARY, Clutter.ButtonState.RELEASED);
                await pause(150);
            },
        };
    }

    disable() {
        delete globalThis.smoke;
    }
}
