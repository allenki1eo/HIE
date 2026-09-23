#include "hie_pipeline.hpp"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static int fails = 0;

#define CHECK(cond, msg)                                   \
    do {                                                   \
        if (!(cond)) {                                     \
            std::fprintf(stderr, "FAIL: %s\n", msg);       \
            ++fails;                                       \
        }                                                  \
    } while (0)

static void fill_rggb(std::vector<uint16_t>& m, int w, int h, float r, float g, float b, uint16_t black,
                      uint16_t white, int shift_x = 0, int shift_y = 0) {
    m.assign(static_cast<size_t>(w) * h, black);
    auto put = [&](int y, int x, uint16_t v) {
        int yy = y + shift_y, xx = x + shift_x;
        if (yy < 0 || xx < 0 || yy >= h || xx >= w) return;
        m[yy * w + xx] = v;
    };
    auto q = [&](float v) -> uint16_t {
        float t = black + v * (white - black);
        if (t < 0) t = 0;
        if (t > 65535) t = 65535;
        return static_cast<uint16_t>(t + 0.5f);
    };
    for (int y = 0; y < h; y += 2) {
        for (int x = 0; x < w; x += 2) {
            // checker so alignment has texture
            float t = (((x / 8) + (y / 8)) & 1) ? 1.f : 0.35f;
            put(y, x, q(r * t));
            put(y, x + 1, q(g * t));
            put(y + 1, x, q(g * t));
            put(y + 1, x + 1, q(b * t));
        }
    }
}

int main() {
    const int w = 64, h = 64;
    const uint16_t black = 64, white = 1023;
    float blk[4] = {64, 64, 64, 64};

    std::vector<uint16_t> a, b;
    fill_rggb(a, w, h, 0.7f, 0.5f, 0.3f, black, white, 0, 0);
    fill_rggb(b, w, h, 0.7f, 0.5f, 0.3f, black, white, 2, 0);  // 2 mosaic px = 1 plane px

    std::vector<float> pa, pb;
    int ph, pw;
    hie::to_planes(a.data(), w, h, w, "RGGB", blk, white, pa, ph, pw);
    hie::to_planes(b.data(), w, h, w, "RGGB", blk, white, pb, ph, pw);
    CHECK(ph == 32 && pw == 32, "plane size");
    CHECK(pa[0] > 0.2f, "R plane non-zero");

    std::vector<float> cfa(static_cast<size_t>(h) * w, 0.f);
    // rebuild mosaic from first frame in linear 0-1 for MHC
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) cfa[y * w + x] = (a[y * w + x] - 64) / 959.f;
    std::vector<float> rgb;
    hie::demosaic_mhc(cfa.data(), h, w, "RGGB", rgb);
    CHECK(rgb.size() == static_cast<size_t>(h) * w * 3, "mhc size");
    CHECK(std::isfinite(rgb[0]) && rgb[0] > 0, "mhc R finite");

    const uint16_t* ptrs[2] = {a.data(), b.data()};
    hie::BurstSpec spec;
    spec.width = w;
    spec.height = h;
    spec.stride_pixels = w;
    spec.n_frames = 2;
    spec.mosaics = ptrs;
    spec.cfa = "RGGB";
    spec.black[0] = spec.black[1] = spec.black[2] = spec.black[3] = 64;
    spec.white = 1023;
    spec.have_noise = true;
    spec.shot[0] = spec.shot[1] = spec.shot[2] = spec.shot[3] = 1e-4f;
    spec.read[0] = spec.read[1] = spec.read[2] = spec.read[3] = 1e-6f;
    spec.wb[0] = 1.6f;
    spec.wb[1] = 1.0f;
    spec.wb[2] = 1.0f;
    spec.wb[3] = 1.8f;
    spec.max_mosaic_pixels = 16'000'000;
    spec.max_frames = 8;
    spec.orientation_deg = 0;

    hie::BurstResult r;
    try {
        r = hie::process_burst(spec);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "process_burst threw: %s\n", e.what());
        return 1;
    }
    CHECK(r.width == 64 && r.height == 64, "output size");
    CHECK(r.rgb.size() == 64u * 64u * 3u, "rgb bytes");
    int nonzero = 0, bright = 0;
    for (unsigned char v : r.rgb) {
        if (v > 8) ++nonzero;
        if (v > 40) ++bright;
    }
    CHECK(nonzero > 1000, "image not black");
    CHECK(bright > 100, "image has midtones");
    CHECK(r.json.find("hie_v0.1") != std::string::npos, "json preset");
    CHECK(r.json.find("hypothesis H1") != std::string::npos, "json records H1 is not implemented");

    // 90° orientation
    spec.orientation_deg = 90;
    auto r2 = hie::process_burst(spec);
    CHECK(r2.width == 64 && r2.height == 64, "rotated square");

    // downsample budget on a larger synthetic
    const int W = 80, H = 48;
    std::vector<uint16_t> big;
    fill_rggb(big, W, H, 0.5f, 0.5f, 0.5f, black, white);
    const uint16_t* one = big.data();
    spec.width = W;
    spec.height = H;
    spec.stride_pixels = W;
    spec.n_frames = 1;
    spec.mosaics = &one;
    spec.orientation_deg = 0;
    spec.max_mosaic_pixels = 1000;  // force 2×
    auto r3 = hie::process_burst(spec);
    CHECK(r3.width == W / 2 && r3.height == H / 2, "2x downsample output");
    CHECK(r3.json.find("2x plane downsample") != std::string::npos, "downsample note");

    if (fails) {
        std::fprintf(stderr, "%d checks failed\n", fails);
        return 1;
    }
    std::printf("hie_host_test: ok  (%dx%d json %zu bytes)\n", r.width, r.height, r.json.size());
    return 0;
}
