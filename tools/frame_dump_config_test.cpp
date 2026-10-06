#include "Q3PWFrameDumpConfig.h"
#include <cassert>
#include <string>

int main() {
    q3pw::FrameDumpConfig config;
    assert(q3pw::ParseFrameDump("C:\\capture with spaces:part:128:9000", config));
    assert(config.directory == "C:\\capture with spaces:part");
    assert(config.count == 128 && config.interval == 9000);
    assert(q3pw::ParseFrameDump("/tmp/cell:3:1", config));
    for (const std::string text : {"", "0", ":1:1", "a:0:1", "a:1:0", "a:129:1", "a:1:9001",
         "a:1", "a:-1:1", "a:+1:1", "a:1:1 ", "a: 1:1", "a:999999999999999999999:1"}) {
        config = {"unchanged", 2, 3};
        assert(!q3pw::ParseFrameDump(text, config));
        assert(config.directory == "unchanged" && config.count == 2 && config.interval == 3);
    }
}
