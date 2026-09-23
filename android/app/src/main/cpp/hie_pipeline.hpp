#pragma once

#include <cstdint>
#include <string>
#include <vector>

// On-device port of the Python hie_v0.1 stages (Hasinoff 2016 tiles + EXP-005
// confidence fusion + N_eff spatial Wiener + MHC + synthetic-exposure tone +
// finish). This is a reproduction, not a new method. H1 is not implemented.

namespace hie {

struct BurstSpec {
    int width = 0;          // mosaic width in pixels
    int height = 0;         // mosaic height in pixels
    int stride_pixels = 0;  // row stride of each packed uint16 buffer
    int n_frames = 0;
    const uint16_t* const* mosaics = nullptr;  // n_frames pointers
    const char* cfa = "RGGB";
    float black[4] = {0, 0, 0, 0};  // R, Gr, Gb, B in sensor counts
    float white = 1023.f;
    float shot[4] = {1e-4f, 1e-4f, 1e-4f, 1e-4f};
    float read[4] = {1e-6f, 1e-6f, 1e-6f, 1e-6f};
    bool have_noise = false;
    float wb[4] = {1, 1, 1, 1};  // R, Gr, Gb, B
    float ccm[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};  // cam → linear sRGB, row-major
    int orientation_deg = 0;  // 0, 90, 180, 270 clockwise
    int max_mosaic_pixels = 16'000'000;  // 2× plane downsample above this
    int max_frames = 8;
};

struct BurstResult {
    std::vector<uint8_t> rgb;  // packed RGB, display-referred sRGB 0–255
    int width = 0;
    int height = 0;
    std::string json;
};

BurstResult process_burst(const BurstSpec& spec);

// Exposed for host tests (same numerics as the on-device path).
void to_planes(const uint16_t* mosaic, int w, int h, int stride, const char* cfa,
               const float black[4], float white, std::vector<float>& planes, int& ph, int& pw);
void demosaic_mhc(const float* cfa, int h, int w, const char* pattern, std::vector<float>& rgb);
void srgb_encode(const float* linear, int n, float* display);
int select_reference(const std::vector<float>& planes, int n, int ph, int pw);
void box_blur(const float* in, int h, int w, int k, float* out);

}  // namespace hie
