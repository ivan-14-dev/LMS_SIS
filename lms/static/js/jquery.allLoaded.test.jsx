const $ = require('jquery');

global.jQuery = $;
require('./jquery.allLoaded');

describe('iframe logout completion', () => {
    it('waits for each iframe once without removing other load handlers', () => {
        const first = $(document.createElement('iframe'));
        const second = $(document.createElement('iframe'));
        const callback = jest.fn();
        const otherHandler = jest.fn();
        first.on('load', otherHandler);
        first.add(second).allLoaded(callback);

        first.triggerHandler('load');
        first.triggerHandler('load');
        expect(callback).not.toHaveBeenCalled();
        expect(otherHandler).toHaveBeenCalledTimes(2);

        second.triggerHandler('load');
        second.triggerHandler('load');
        expect(callback).toHaveBeenCalledTimes(1);
        expect(callback.mock.contexts[0]).toBe(window);
    });
});
