// Copyright (c) 2026 Quest3-Pyrowave contributors
// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace Framebank
{
inline uint32_t positive_integer(const std::string &value)
{
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("invalid positive integer");
    auto n = std::stoull(value);
    if (!n || n > 0xffffffffull) throw std::runtime_error("integer out of range");
    return uint32_t(n);
}

class RawY4M
{
    std::ifstream input;
    std::string line()
    {
        std::string value;
        char c;
        while (input.get(c))
        {
            if (c == '\n') return value;
            if (value.size() >= 4096) throw std::runtime_error("Y4M line too long");
            value += c;
        }
        throw std::runtime_error("incomplete Y4M line");
    }
public:
    uint32_t width = 0, height = 0, fps_num = 0, fps_den = 0;
    bool subsampled = false, full_range = false;
    std::string chroma;
    explicit RawY4M(const std::string &path) : input(path, std::ios::binary)
    {
        if (!input) throw std::runtime_error("cannot open Y4M");
        std::istringstream header(line());
        std::string token;
        header >> token;
        if (token != "YUV4MPEG2") throw std::runtime_error("invalid Y4M magic");
        bool range_present = false;
        while (header >> token)
        {
            if (token[0] == 'W' && !width) width = positive_integer(token.substr(1));
            else if (token[0] == 'H' && !height) height = positive_integer(token.substr(1));
            else if (token[0] == 'F' && !fps_num)
            {
                auto colon = token.find(':');
                if (colon == std::string::npos) throw std::runtime_error("invalid Y4M frame rate");
                fps_num = positive_integer(token.substr(1, colon - 1));
                fps_den = positive_integer(token.substr(colon + 1));
            }
            else if (token[0] == 'C' && chroma.empty()) chroma = token;
            else if (token == "XCOLORRANGE=FULL" && !range_present) { full_range = true; range_present = true; }
            else if (token == "XCOLORRANGE=LIMITED" && !range_present) { range_present = true; }
            else if (token[0] == 'W' || token[0] == 'H' || token[0] == 'F' || token[0] == 'C' ||
                     token.find("XCOLORRANGE=") == 0) throw std::runtime_error("duplicate or unsupported Y4M field");
        }
        if (!width || !height || !fps_num || !fps_den || !range_present ||
            uint64_t(width) * height > 64ull * 1024 * 1024)
            throw std::runtime_error("incomplete or excessive Y4M geometry");
        subsampled = chroma == "C420jpeg";
        if ((!subsampled && chroma != "C444") || (subsampled && ((width | height) & 1)))
            throw std::runtime_error("only even 8-bit C420jpeg or C444 is supported");
    }
    bool same_format(const RawY4M &other) const
    {
        return width == other.width && height == other.height && chroma == other.chroma &&
               full_range == other.full_range && fps_num == other.fps_num && fps_den == other.fps_den;
    }
    void read_frame(std::vector<uint8_t> &luma)
    {
        if (line() != "FRAME") throw std::runtime_error("missing Y4M frame marker");
        luma.resize(size_t(width) * height);
        if (!input.read(reinterpret_cast<char *>(luma.data()), std::streamsize(luma.size())))
            throw std::runtime_error("incomplete Y4M luma");
        size_t remaining = subsampled ? luma.size() / 2 : luma.size() * 2;
        char discard[16384];
        while (remaining)
        {
            size_t chunk = remaining < sizeof(discard) ? remaining : sizeof(discard);
            if (!input.read(discard, std::streamsize(chunk))) throw std::runtime_error("incomplete Y4M chroma");
            remaining -= chunk;
        }
    }
    bool at_end() { return input.peek() == std::char_traits<char>::eof(); }
};
}
