#include "hie_pipeline.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstring>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace hie {
namespace {

using clock = std::chrono::steady_clock;
using c32 = std::complex<float>;

constexpr float kPi = 3.14159265358979323846f;
constexpr int kTile = 16;
constexpr float kPyrVar[] = {1.f, 0.0748f, 0.0152f, 0.00363f, 0.000899f, 0.00023f, 5.8e-05f};
constexpr float kPyrInfl[] = {1.f, 1.71f, 1.99f, 2.f, 2.f, 2.f, 2.f};

struct Timer {
    std::vector<std::pair<std::string, double>> items;
    double total = 0;
    struct Scope {
        Timer* t;
        const char* name;
        clock::time_point a;
        ~Scope() {
            double s = std::chrono::duration<double>(clock::now() - a).count();
            t->items.emplace_back(name, s);
            t->total += s;
        }
    };
    Scope scope(const char* name) { return Scope{this, name, clock::now()}; }
};

int reflect101(int i, int n) {
    if (n <= 1) return 0;
    while (i < 0 || i >= n) {
        if (i < 0) i = -i;
        if (i >= n) i = 2 * n - 2 - i;
    }
    return i;
}

int clampi(int v, int lo, int hi) { return std::max(lo, std::min(hi, v)); }

struct Plane4 {
    int h = 0, w = 0;
    std::vector<float> data;  // (h, w, 4)
    void alloc(int hh, int ww) {
        h = hh;
        w = ww;
        data.assign(static_cast<size_t>(h) * w * 4, 0.f);
    }
    float* pix(int y, int x) { return data.data() + (static_cast<size_t>(y) * w + x) * 4; }
    const float* pix(int y, int x) const { return data.data() + (static_cast<size_t>(y) * w + x) * 4; }
};

struct Gray {
    int h = 0, w = 0;
    std::vector<float> data;
    void alloc(int hh, int ww) {
        h = hh;
        w = ww;
        data.assign(static_cast<size_t>(h) * w, 0.f);
    }
    float& at(int y, int x) { return data[static_cast<size_t>(y) * w + x]; }
    float at(int y, int x) const { return data[static_cast<size_t>(y) * w + x]; }
};

struct Offs {
    int r[4], c[4];  // R, Gr, Gb, B
};

bool parse_cfa(const char* pat, Offs& o) {
    std::string p = pat ? pat : "RGGB";
    for (char& ch : p) ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
    if (p.size() != 4) return false;
    char grid[2][2] = {{p[0], p[1]}, {p[2], p[3]}};
    bool seen[4] = {};
    for (int r = 0; r < 2; ++r) {
        for (int c = 0; c < 2; ++c) {
            char col = grid[r][c];
            int idx = -1;
            if (col == 'R') idx = 0;
            else if (col == 'B') idx = 3;
            else if (col == 'G') {
                char other = grid[r][1 - c];
                idx = (other == 'R') ? 1 : 2;
            } else return false;
            o.r[idx] = r;
            o.c[idx] = c;
            seen[idx] = true;
        }
    }
    return seen[0] && seen[1] && seen[2] && seen[3];
}

void planes_to_gray(const Plane4& p, Gray& g) {
    g.alloc(p.h, p.w);
    const size_t n = static_cast<size_t>(p.h) * p.w;
    for (size_t i = 0; i < n; ++i) {
        const float* v = p.data.data() + i * 4;
        g.data[i] = 0.25f * (v[0] + v[1] + v[2] + v[3]);
    }
}

void downsample2(const Plane4& in, Plane4& out) {
    int nh = in.h / 2, nw = in.w / 2;
    if (nh < 1 || nw < 1) {
        out = in;
        return;
    }
    out.alloc(nh, nw);
    for (int y = 0; y < nh; ++y) {
        for (int x = 0; x < nw; ++x) {
            float acc[4] = {};
            for (int dy = 0; dy < 2; ++dy)
                for (int dx = 0; dx < 2; ++dx) {
                    const float* p = in.pix(y * 2 + dy, x * 2 + dx);
                    for (int c = 0; c < 4; ++c) acc[c] += p[c];
                }
            float* o = out.pix(y, x);
            for (int c = 0; c < 4; ++c) o[c] = acc[c] * 0.25f;
        }
    }
}

// OpenCV-style 5-tap pyrDown: kernel [1,4,6,4,1]/16, even samples.
void pyr_down(const Gray& in, Gray& out) {
    const int nh = std::max(1, in.h / 2);
    const int nw = std::max(1, in.w / 2);
    Gray tmp;
    tmp.alloc(in.h, nw);
    const float k[5] = {1.f, 4.f, 6.f, 4.f, 1.f};
    for (int y = 0; y < in.h; ++y) {
        for (int x = 0; x < nw; ++x) {
            int sx = x * 2;
            float s = 0;
            for (int t = -2; t <= 2; ++t) s += k[t + 2] * in.at(y, reflect101(sx + t, in.w));
            tmp.at(y, x) = s / 16.f;
        }
    }
    out.alloc(nh, nw);
    for (int y = 0; y < nh; ++y) {
        int sy = y * 2;
        for (int x = 0; x < nw; ++x) {
            float s = 0;
            for (int t = -2; t <= 2; ++t) s += k[t + 2] * tmp.at(reflect101(sy + t, in.h), x);
            out.at(y, x) = s / 16.f;
        }
    }
}

void pyr_up(const Gray& in, Gray& out, int oh, int ow) {
    out.alloc(oh, ow);
    std::fill(out.data.begin(), out.data.end(), 0.f);
    const float k[5] = {1.f, 4.f, 6.f, 4.f, 1.f};
    Gray tmp;
    tmp.alloc(in.h, ow);
    for (int y = 0; y < in.h; ++y) {
        for (int x = 0; x < ow; ++x) {
            float s = 0, w = 0;
            for (int t = -2; t <= 2; ++t) {
                int src = x - t;
                if (src % 2) continue;
                src /= 2;
                if (src < 0 || src >= in.w) continue;
                s += k[t + 2] * in.at(y, src);
                w += k[t + 2];
            }
            tmp.at(y, x) = (w > 0) ? s / 8.f : 0;  // OpenCV pyrUp gain
        }
    }
    for (int y = 0; y < oh; ++y) {
        for (int x = 0; x < ow; ++x) {
            float s = 0, w = 0;
            for (int t = -2; t <= 2; ++t) {
                int src = y - t;
                if (src % 2) continue;
                src /= 2;
                if (src < 0 || src >= in.h) continue;
                s += k[t + 2] * tmp.at(src, x);
                w += k[t + 2];
            }
            out.at(y, x) = (w > 0) ? s / 8.f : 0;
        }
    }
}

void box_blur_impl(const float* in, int h, int w, int win, float* out) {
    const int r = win / 2;
    std::vector<float> tmp(static_cast<size_t>(h) * w);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float s = 0;
            for (int k = -r; k <= r; ++k) s += in[y * w + reflect101(x + k, w)];
            tmp[y * w + x] = s / static_cast<float>(win);
        }
    }
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float s = 0;
            for (int k = -r; k <= r; ++k) s += tmp[reflect101(y + k, h) * w + x];
            out[y * w + x] = s / static_cast<float>(win);
        }
    }
}

void gauss_sigma1(const float* in, int h, int w, float* out) {
    // Separable σ≈1, 5-tap
    const float k[5] = {0.06136f, 0.24477f, 0.38774f, 0.24477f, 0.06136f};
    std::vector<float> tmp(static_cast<size_t>(h) * w);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float s = 0;
            for (int t = -2; t <= 2; ++t) s += k[t + 2] * in[y * w + reflect101(x + t, w)];
            tmp[y * w + x] = s;
        }
    }
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float s = 0;
            for (int t = -2; t <= 2; ++t) s += k[t + 2] * tmp[reflect101(y + t, h) * w + x];
            out[y * w + x] = s;
        }
    }
}

float frame_sharpness(const Plane4& p) {
    Gray g;
    planes_to_gray(p, g);
    std::vector<float> blur(g.data.size()), lap(g.data.size());
    gauss_sigma1(g.data.data(), g.h, g.w, blur.data());
    for (int y = 0; y < g.h; ++y) {
        for (int x = 0; x < g.w; ++x) {
            float c = blur[y * g.w + x];
            float n = blur[reflect101(y - 1, g.h) * g.w + x];
            float s = blur[reflect101(y + 1, g.h) * g.w + x];
            float w = blur[y * g.w + reflect101(x - 1, g.w)];
            float e = blur[y * g.w + reflect101(x + 1, g.w)];
            float L = n + s + w + e - 4.f * c;
            lap[y * g.w + x] = L * L;
        }
    }
    double acc = 0;
    for (float v : lap) acc += v;
    return static_cast<float>(acc / lap.size());
}

void conv2d(const float* in, int h, int w, const float* ker, int k, float* out) {
    const int r = k / 2;
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float s = 0;
            for (int ky = 0; ky < k; ++ky) {
                for (int kx = 0; kx < k; ++kx) {
                    int iy = reflect101(y + ky - r, h);
                    int ix = reflect101(x + kx - r, w);
                    s += in[iy * w + ix] * ker[ky * k + kx];
                }
            }
            out[y * w + x] = s;
        }
    }
}

// ---------------- FFT 16 (radix-2, unnormalised forward; inverse / n) ----
void bitrev16(c32* a) {
    constexpr int rev[16] = {0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15};
    for (int i = 0; i < 16; ++i) {
        if (i < rev[i]) std::swap(a[i], a[rev[i]]);
    }
}

void fft16(c32* a, bool inverse) {
    bitrev16(a);
    for (int len = 2; len <= 16; len <<= 1) {
        float ang = (inverse ? 2.f : -2.f) * kPi / static_cast<float>(len);
        c32 wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < 16; i += len) {
            c32 w(1.f, 0.f);
            for (int j = 0; j < len / 2; ++j) {
                c32 u = a[i + j];
                c32 v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
    if (inverse) {
        for (int i = 0; i < 16; ++i) a[i] /= 16.f;
    }
}

void fft2_16(c32 img[16][16], bool inverse) {
    c32 row[16];
    for (int y = 0; y < 16; ++y) {
        for (int x = 0; x < 16; ++x) row[x] = img[y][x];
        fft16(row, inverse);
        for (int x = 0; x < 16; ++x) img[y][x] = row[x];
    }
    for (int x = 0; x < 16; ++x) {
        for (int y = 0; y < 16; ++y) row[y] = img[y][x];
        fft16(row, inverse);
        for (int y = 0; y < 16; ++y) img[y][x] = row[y];
    }
}

void raised_cosine(float w[16][16]) {
    float w1[16];
    for (int x = 0; x < 16; ++x) w1[x] = 0.5f - 0.5f * std::cos(2.f * kPi * (x + 0.5f) / 16.f);
    for (int y = 0; y < 16; ++y)
        for (int x = 0; x < 16; ++x) w[y][x] = w1[y] * w1[x];
}

void reflect_pad(const float* img, int h, int w, int c, int pt, int pb, int pl, int pr,
                 std::vector<float>& out, int& oh, int& ow) {
    oh = h + pt + pb;
    ow = w + pl + pr;
    out.assign(static_cast<size_t>(oh) * ow * c, 0.f);
    for (int y = 0; y < oh; ++y) {
        int iy = reflect101(y - pt, h);
        for (int x = 0; x < ow; ++x) {
            int ix = reflect101(x - pl, w);
            const float* s = img + (static_cast<size_t>(iy) * w + ix) * c;
            float* d = out.data() + (static_cast<size_t>(y) * ow + x) * c;
            for (int k = 0; k < c; ++k) d[k] = s[k];
        }
    }
}

void spatial_wiener(const Plane4& planes, const std::vector<float>& var /*h*w*4*/, float strength,
                    Plane4& out) {
    out.alloc(planes.h, planes.w);
    if (strength <= 0) {
        out.data = planes.data;
        return;
    }
    const int T = kTile;
    const int s = T / 2;
    int extra_h = (-(planes.h + 2 * s - T)) % s;
    if (extra_h < 0) extra_h += s;
    int extra_w = (-(planes.w + 2 * s - T)) % s;
    if (extra_w < 0) extra_w += s;
    std::vector<float> padP, padV;
    int ph, pw, vh, vw;
    reflect_pad(planes.data.data(), planes.h, planes.w, 4, s, s + extra_h, s, s + extra_w, padP, ph, pw);
    reflect_pad(var.data(), planes.h, planes.w, 4, s, s + extra_h, s, s + extra_w, padV, vh, vw);
    std::vector<float> acc(padP.size(), 0.f);
    float win[16][16];
    raised_cosine(win);
    const int ny = 1 + (ph - T) / s;
    const int nx = 1 + (pw - T) / s;
    for (int ty = 0; ty < ny; ++ty) {
        for (int tx = 0; tx < nx; ++tx) {
            int y0 = ty * s, x0 = tx * s;
            for (int ch = 0; ch < 4; ++ch) {
                c32 F[16][16];
                float vmean = 0;
                for (int y = 0; y < T; ++y) {
                    for (int x = 0; x < T; ++x) {
                        size_t idx = (static_cast<size_t>(y0 + y) * pw + (x0 + x)) * 4 + ch;
                        F[y][x] = c32(padP[idx], 0.f);
                        vmean += padV[idx];
                    }
                }
                vmean /= static_cast<float>(T * T);
                fft2_16(F, false);
                const float noise = strength * T * T * vmean;
                for (int y = 0; y < T; ++y) {
                    for (int x = 0; x < T; ++x) {
                        float p = F[y][x].real() * F[y][x].real() + F[y][x].imag() * F[y][x].imag();
                        float g = p / (p + noise + 1e-20f);
                        if (y == 0 && x == 0) g = 1.f;
                        F[y][x] *= g;
                    }
                }
                fft2_16(F, true);
                for (int y = 0; y < T; ++y) {
                    for (int x = 0; x < T; ++x) {
                        size_t idx = (static_cast<size_t>(y0 + y) * pw + (x0 + x)) * 4 + ch;
                        acc[idx] += F[y][x].real() * win[y][x];
                    }
                }
            }
        }
    }
    for (int y = 0; y < planes.h; ++y) {
        for (int x = 0; x < planes.w; ++x) {
            float* d = out.pix(y, x);
            const float* src = acc.data() + (static_cast<size_t>(y + s) * pw + (x + s)) * 4;
            for (int c = 0; c < 4; ++c) d[c] = src[c];
        }
    }
}

// ---------------- alignment ------------------------------------------------
void gather_tile(const Gray& img, int ty, int tx, int tile, int dy, int dx, float* dst) {
    for (int y = 0; y < tile; ++y) {
        int iy = clampi(ty + dy + y, 0, img.h - 1);
        for (int x = 0; x < tile; ++x) {
            int ix = clampi(tx + dx + x, 0, img.w - 1);
            dst[y * tile + x] = img.at(iy, ix);
        }
    }
}

float tile_cost(const float* a, const float* b, int tile, bool l1) {
    float s = 0;
    const int n = tile * tile;
    if (l1) {
        for (int i = 0; i < n; ++i) s += std::fabs(a[i] - b[i]);
    } else {
        for (int i = 0; i < n; ++i) {
            float d = a[i] - b[i];
            s += d * d;
        }
    }
    return s;
}

bool tile_inside(int h, int w, int ty, int tx, int tile, int dy, int dx) {
    int half = tile / 2;
    int y = ty + dy, x = tx + dx;
    return y >= -half && y + tile <= h + half && x >= -half && x + tile <= w + half;
}

void densify(const std::vector<float>& tile_dx, const std::vector<float>& tile_dy, int ny, int nx,
             int stride, int tile, int h, int w, std::vector<float>& flow /* h*w*2 dx,dy */) {
    flow.assign(static_cast<size_t>(h) * w * 2, 0.f);
    const float centre = (tile - 1) * 0.5f;
    for (int y = 0; y < h; ++y) {
        float gy = (static_cast<float>(y) - centre) / static_cast<float>(stride);
        int y0 = static_cast<int>(std::floor(gy));
        float fy = gy - y0;
        int y1 = y0 + 1;
        y0 = clampi(y0, 0, ny - 1);
        y1 = clampi(y1, 0, ny - 1);
        for (int x = 0; x < w; ++x) {
            float gx = (static_cast<float>(x) - centre) / static_cast<float>(stride);
            int x0 = static_cast<int>(std::floor(gx));
            float fx = gx - x0;
            int x1 = x0 + 1;
            x0 = clampi(x0, 0, nx - 1);
            x1 = clampi(x1, 0, nx - 1);
            auto sample = [&](int iy, int ix, const std::vector<float>& t) {
                return t[static_cast<size_t>(iy) * nx + ix];
            };
            float dx = (1 - fy) * ((1 - fx) * sample(y0, x0, tile_dx) + fx * sample(y0, x1, tile_dx)) +
                       fy * ((1 - fx) * sample(y1, x0, tile_dx) + fx * sample(y1, x1, tile_dx));
            float dy = (1 - fy) * ((1 - fx) * sample(y0, x0, tile_dy) + fx * sample(y0, x1, tile_dy)) +
                       fy * ((1 - fx) * sample(y1, x0, tile_dy) + fx * sample(y1, x1, tile_dy));
            flow[(static_cast<size_t>(y) * w + x) * 2 + 0] = dx;
            flow[(static_cast<size_t>(y) * w + x) * 2 + 1] = dy;
        }
    }
}

void align_tiles(const Gray& ref, const Gray& alt, const float shot_mean, const float read_mean,
                 bool have_noise, std::vector<float>& flow, float& mean_disp) {
    const int tile_sizes[] = {16, 16, 16, 16, 8};
    const int factors[] = {1, 2, 2, 2, 4};
    const int radii[] = {1, 2, 2, 2, 4};
    const bool l1norm[] = {true, false, false, false, false};
    const float significance = 3.f;

    std::vector<Gray> pr, pa;
    pr.push_back(ref);
    pa.push_back(alt);
    for (int lvl = 1; lvl < 5; ++lvl) {
        int steps = 0;
        int f = factors[lvl];
        while (f > 1) {
            f /= 2;
            ++steps;
        }
        Gray nr = pr.back(), na = pa.back();
        for (int s = 0; s < steps; ++s) {
            Gray tmp;
            pyr_down(nr, tmp);
            nr = std::move(tmp);
            pyr_down(na, tmp);
            na = std::move(tmp);
        }
        if (std::min(nr.h, nr.w) < 2 * tile_sizes[lvl]) break;
        pr.push_back(std::move(nr));
        pa.push_back(std::move(na));
    }
    const int levels = static_cast<int>(pr.size());
    int n_pyr[8] = {0};
    int acc_down = 0;
    for (int i = 1; i < levels; ++i) {
        int f = factors[i];
        int steps = 0;
        while (f > 1) {
            f /= 2;
            ++steps;
        }
        acc_down += steps;
        n_pyr[i] = acc_down;
    }

    std::vector<float> disp_dy, disp_dx;  // current level, size ny*nx
    int c_ny = 0, c_nx = 0, c_stride = 0, c_tile = 0;

    auto noise_std = [&](const float* tiles, int ntiles, int tile, bool l1, int n_down, std::vector<float>& out) {
        out.assign(ntiles, 0.f);
        if (!have_noise) return;
        n_down = std::min(n_down, 6);
        const float corr = kPyrInfl[n_down];
        const float pv = kPyrVar[n_down];
        for (int i = 0; i < ntiles; ++i) {
            float mean = 0;
            const int N = tile * tile;
            for (int k = 0; k < N; ++k) mean += tiles[i * N + k];
            mean = std::max(mean / N, 0.f);
            float v = (shot_mean * mean + read_mean) * 0.25f * pv;
            if (l1) {
                out[i] = std::sqrt(2.f) * tile * std::sqrt(2.f * v * (1.f - 2.f / kPi) * corr);
            } else {
                out[i] = std::sqrt(2.f) * 2.f * std::sqrt(2.f) * v * tile * std::sqrt(corr);
            }
        }
    };

    for (int lvl = levels - 1; lvl >= 0; --lvl) {
        const Gray& R = pr[lvl];
        const Gray& A = pa[lvl];
        int tile = std::min(tile_sizes[lvl], std::min(R.h, R.w));
        int stride = (lvl == 0) ? tile / 2 : tile;
        if (stride < 1) stride = 1;
        int ny = (R.h + stride - 1) / stride;
        int nx = (R.w + stride - 1) / stride;
        const int n = ny * nx;
        std::vector<int> ty(n), tx(n);
        std::vector<float> ref_tiles(static_cast<size_t>(n) * tile * tile);
        for (int i = 0; i < ny; ++i) {
            for (int j = 0; j < nx; ++j) {
                int id = i * nx + j;
                ty[id] = i * stride;
                tx[id] = j * stride;
                gather_tile(R, ty[id], tx[id], tile, 0, 0, ref_tiles.data() + static_cast<size_t>(id) * tile * tile);
            }
        }
        std::vector<int> prior_dy(n, 0), prior_dx(n, 0);
        if (!disp_dy.empty()) {
            // propagate 3 candidates from coarse
            std::vector<float> alt_buf(static_cast<size_t>(tile) * tile);
            for (int id = 0; id < n; ++id) {
                float cy = (ty[id] + tile * 0.5f) / static_cast<float>(factors[lvl + 1]);
                float cx = (tx[id] + tile * 0.5f) / static_cast<float>(factors[lvl + 1]);
                int ci = clampi(static_cast<int>(std::floor(cy / c_stride)), 0, c_ny - 1);
                int cj = clampi(static_cast<int>(std::floor(cx / c_stride)), 0, c_nx - 1);
                int ni = clampi((cy - ci * c_stride < c_stride * 0.5f) ? ci - 1 : ci + 1, 0, c_ny - 1);
                int nj = clampi((cx - cj * c_stride < c_stride * 0.5f) ? cj - 1 : cj + 1, 0, c_nx - 1);
                int cands[3][2];
                int ids[3] = {ci * c_nx + cj, ni * c_nx + cj, ci * c_nx + nj};
                for (int k = 0; k < 3; ++k) {
                    cands[k][0] = static_cast<int>(std::lround(disp_dy[ids[k]] * factors[lvl + 1]));
                    cands[k][1] = static_cast<int>(std::lround(disp_dx[ids[k]] * factors[lvl + 1]));
                }
                const float* rt = ref_tiles.data() + static_cast<size_t>(id) * tile * tile;
                float bestc = 1e30f;
                int bestk = 0;
                int finite = 0;
                for (int k = 0; k < 3; ++k) {
                    float cost = 1e30f;
                    if (tile_inside(A.h, A.w, ty[id], tx[id], tile, cands[k][0], cands[k][1])) {
                        gather_tile(A, ty[id], tx[id], tile, cands[k][0], cands[k][1], alt_buf.data());
                        cost = tile_cost(rt, alt_buf.data(), tile, true);
                        ++finite;
                    }
                    if (k == 0 && finite == 0) cost = 0;  // keep enclosing
                    if (cost < bestc) {
                        bestc = cost;
                        bestk = k;
                    }
                }
                prior_dy[id] = cands[bestk][0];
                prior_dx[id] = cands[bestk][1];
            }
        }

        std::vector<float> cost_std;
        noise_std(ref_tiles.data(), n, tile, l1norm[lvl], n_pyr[lvl], cost_std);
        std::vector<int> best_dy = prior_dy, best_dx = prior_dx;
        std::vector<float> best_cost(n, 1e30f), prior_cost(n, 1e30f);
        std::vector<float> alt_buf(static_cast<size_t>(tile) * tile);
        const int rad = radii[lvl];
        for (int oy = -rad; oy <= rad; ++oy) {
            for (int ox = -rad; ox <= rad; ++ox) {
                for (int id = 0; id < n; ++id) {
                    int dy = prior_dy[id] + oy;
                    int dx = prior_dx[id] + ox;
                    const float* rt = ref_tiles.data() + static_cast<size_t>(id) * tile * tile;
                    gather_tile(A, ty[id], tx[id], tile, dy, dx, alt_buf.data());
                    float cost = tile_cost(rt, alt_buf.data(), tile, l1norm[lvl]);
                    if (oy || ox) {
                        if (!tile_inside(A.h, A.w, ty[id], tx[id], tile, dy, dx)) cost = 1e30f;
                    }
                    if (oy == 0 && ox == 0) prior_cost[id] = cost;
                    if (cost < best_cost[id] - 1e-9f) {
                        best_cost[id] = cost;
                        best_dy[id] = dy;
                        best_dx[id] = dx;
                    }
                }
            }
        }
        if (have_noise) {
            for (int id = 0; id < n; ++id) {
                if ((prior_cost[id] - best_cost[id]) < significance * cost_std[id]) {
                    best_dy[id] = prior_dy[id];
                    best_dx[id] = prior_dx[id];
                    best_cost[id] = prior_cost[id];
                }
            }
        }

        std::vector<float> sub_y(n, 0.f), sub_x(n, 0.f);
        {
            std::vector<float> cL(n), cR(n), cU(n), cD(n), c0(n);
            std::vector<float> buf(static_cast<size_t>(tile) * tile);
            for (int id = 0; id < n; ++id) {
                const float* rt = ref_tiles.data() + static_cast<size_t>(id) * tile * tile;
                auto cost_at = [&](int oy, int ox) {
                    gather_tile(A, ty[id], tx[id], tile, best_dy[id] + oy, best_dx[id] + ox, buf.data());
                    return tile_cost(rt, buf.data(), tile, false);
                };
                c0[id] = cost_at(0, 0);
                cU[id] = cost_at(-1, 0);
                cD[id] = cost_at(1, 0);
                cL[id] = cost_at(0, -1);
                cR[id] = cost_at(0, 1);
            }
            std::vector<float> l2std;
            noise_std(ref_tiles.data(), n, tile, false, n_pyr[lvl], l2std);
            auto vertex = [](float cm, float c0, float cp) {
                float den = cm - 2 * c0 + cp;
                if (den <= 1e-12f) return 0.f;
                return std::max(-0.5f, std::min(0.5f, 0.5f * (cm - cp) / den));
            };
            for (int id = 0; id < n; ++id) {
                sub_y[id] = vertex(cU[id], c0[id], cD[id]);
                sub_x[id] = vertex(cL[id], c0[id], cR[id]);
                if (have_noise) {
                    if (cU[id] - 2 * c0[id] + cD[id] <= significance * l2std[id]) sub_y[id] = 0;
                    if (cL[id] - 2 * c0[id] + cR[id] <= significance * l2std[id]) sub_x[id] = 0;
                }
            }
        }
        disp_dy.resize(n);
        disp_dx.resize(n);
        for (int i = 0; i < n; ++i) {
            disp_dy[i] = static_cast<float>(best_dy[i]) + sub_y[i];
            disp_dx[i] = static_cast<float>(best_dx[i]) + sub_x[i];
        }
        c_ny = ny;
        c_nx = nx;
        c_stride = stride;
        c_tile = tile;
    }

    densify(disp_dx, disp_dy, c_ny, c_nx, c_stride, c_tile, ref.h, ref.w, flow);
    double mx = 0, my = 0;
    const size_t np = static_cast<size_t>(ref.h) * ref.w;
    for (size_t i = 0; i < np; ++i) {
        mx += flow[i * 2];
        my += flow[i * 2 + 1];
    }
    mx /= static_cast<double>(np);
    my /= static_cast<double>(np);
    mean_disp = static_cast<float>(std::sqrt(mx * mx + my * my));
}

float cubic_hermite(float a, float b, float c, float d, float t) {
    float t2 = t * t, t3 = t2 * t;
    return 0.5f * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
}

void warp_cubic(const Plane4& src, const std::vector<float>& flow, Plane4& dst, std::vector<uint8_t>& valid) {
    dst.alloc(src.h, src.w);
    valid.assign(static_cast<size_t>(src.h) * src.w, 0);
    auto sample = [&](float y, float x, float* o) {
        int x1 = static_cast<int>(std::floor(x));
        int y1 = static_cast<int>(std::floor(y));
        float fx = x - x1;
        float fy = y - y1;
        float col[4][4];
        for (int c = 0; c < 4; ++c) {
            float rows[4];
            for (int m = -1; m <= 2; ++m) {
                int iy = clampi(y1 + m, 0, src.h - 1);
                float p[4];
                for (int n = -1; n <= 2; ++n) {
                    int ix = clampi(x1 + n, 0, src.w - 1);
                    p[n + 1] = src.pix(iy, ix)[c];
                }
                rows[m + 1] = cubic_hermite(p[0], p[1], p[2], p[3], fx);
            }
            o[c] = cubic_hermite(rows[0], rows[1], rows[2], rows[3], fy);
        }
    };
    for (int y = 0; y < src.h; ++y) {
        for (int x = 0; x < src.w; ++x) {
            float dx = flow[(static_cast<size_t>(y) * src.w + x) * 2 + 0];
            float dy = flow[(static_cast<size_t>(y) * src.w + x) * 2 + 1];
            float sx = x + dx;
            float sy = y + dy;
            sample(sy, sx, dst.pix(y, x));
            valid[static_cast<size_t>(y) * src.w + x] =
                (sx >= 0 && sx <= src.w - 1 && sy >= 0 && sy <= src.h - 1) ? 1 : 0;
        }
    }
}

void normalized_residual(const Plane4& ref, const Plane4& alt, const float shot[4], const float readn[4],
                         int window, std::vector<float>& d2) {
    const int h = ref.h, w = ref.w;
    std::vector<float> smooth(static_cast<size_t>(h) * w * 4);
    std::vector<float> ch(static_cast<size_t>(h) * w), sm(static_cast<size_t>(h) * w);
    for (int c = 0; c < 4; ++c) {
        for (int i = 0; i < h * w; ++i) ch[i] = ref.data[i * 4 + c];
        box_blur_impl(ch.data(), h, w, 3, sm.data());
        for (int i = 0; i < h * w; ++i) smooth[i * 4 + c] = sm[i];
    }
    std::vector<float> d2ch(static_cast<size_t>(h) * w, 0.f);
    for (int i = 0; i < h * w; ++i) {
        float acc = 0;
        for (int c = 0; c < 4; ++c) {
            float x = std::max(smooth[i * 4 + c], 0.f);
            float var = shot[c] * x + readn[c];
            float d = alt.data[i * 4 + c] - ref.data[i * 4 + c];
            acc += (d * d) / (2.f * var + 1e-12f);
        }
        d2ch[i] = acc * 0.25f;
    }
    d2.resize(static_cast<size_t>(h) * w);
    box_blur_impl(d2ch.data(), h, w, window, d2.data());
}

void estimate_noise(const std::vector<Plane4>& frames, float shot[4], float readn[4]) {
    if (frames.size() < 3) {
        for (int c = 0; c < 4; ++c) {
            shot[c] = 1e-4f;
            readn[c] = 1e-6f;
        }
        return;
    }
    const int h = frames[0].h, w = frames[0].w;
    const int n = static_cast<int>(frames.size());
    for (int c = 0; c < 4; ++c) {
        double sx = 0, sy = 0, sxx = 0, sxy = 0;
        int cnt = 0;
        const int step = std::max(1, std::min(h, w) / 64);
        for (int y = 0; y < h; y += step) {
            for (int x = 0; x < w; x += step) {
                double mean = 0, m2 = 0;
                for (int z = 0; z < n; ++z) {
                    float v = frames[z].pix(y, x)[c];
                    mean += v;
                }
                mean /= n;
                for (int z = 0; z < n; ++z) {
                    double d = frames[z].pix(y, x)[c] - mean;
                    m2 += d * d;
                }
                double var = m2 / (n - 1);
                if (mean < 0.02 || mean > 0.85) continue;
                sx += mean;
                sy += var;
                sxx += mean * mean;
                sxy += mean * var;
                ++cnt;
            }
        }
        if (cnt < 8) {
            shot[c] = 1e-4f;
            readn[c] = 1e-6f;
            continue;
        }
        double den = cnt * sxx - sx * sx;
        double S = (den > 1e-12) ? (cnt * sxy - sx * sy) / den : 0;
        double O = (sy - S * sx) / cnt;
        if (S < 0) {
            S = 0;
            O = sy / cnt;
        }
        if (O < 0) {
            O = 0;
            S = (sxx > 0) ? sxy / sxx : 1e-4;
        }
        shot[c] = static_cast<float>(S);
        readn[c] = static_cast<float>(O);
    }
}

void from_planes(const Plane4& p, const Offs& o, std::vector<float>& cfa, int& ch, int& cw) {
    ch = p.h * 2;
    cw = p.w * 2;
    cfa.assign(static_cast<size_t>(ch) * cw, 0.f);
    for (int i = 0; i < 4; ++i) {
        for (int y = 0; y < p.h; ++y) {
            for (int x = 0; x < p.w; ++x) {
                cfa[(y * 2 + o.r[i]) * cw + (x * 2 + o.c[i])] = p.pix(y, x)[i];
            }
        }
    }
}

void apply_matrix(const std::vector<float>& rgb, int n, const float m[9], std::vector<float>& out) {
    out.resize(static_cast<size_t>(n) * 3);
    for (int i = 0; i < n; ++i) {
        const float* v = rgb.data() + i * 3;
        out[i * 3 + 0] = m[0] * v[0] + m[1] * v[1] + m[2] * v[2];
        out[i * 3 + 1] = m[3] * v[0] + m[4] * v[1] + m[5] * v[2];
        out[i * 3 + 2] = m[6] * v[0] + m[7] * v[1] + m[8] * v[2];
    }
}

float luminance_pix(float r, float g, float b) { return 0.2126f * r + 0.7152f * g + 0.0722f * b; }

void srgb_encode_n(const float* x, int n, float* y) {
    for (int i = 0; i < n; ++i) {
        float v = std::min(1.f, std::max(0.f, x[i]));
        y[i] = (v <= 0.0031308f) ? 12.92f * v : 1.055f * std::pow(v, 1.f / 2.4f) - 0.055f;
    }
}

void srgb_decode_n(const float* x, int n, float* y) {
    for (int i = 0; i < n; ++i) {
        float v = std::min(1.f, std::max(0.f, x[i]));
        y[i] = (v <= 0.04045f) ? v / 12.92f : std::pow((v + 0.055f) / 1.055f, 2.4f);
    }
}

void compress_gamut(std::vector<float>& rgb, int n) {
    for (int i = 0; i < n; ++i) {
        float r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
        float y = std::min(1.f, std::max(0.f, luminance_pix(r, g, b)));
        float over = std::max(std::max(r, g), std::max(b, 1.f));
        float under = std::min(std::min(r, g), std::min(b, 0.f));
        float t_hi = (over > 1.f) ? (1.f - y) / std::max(over - y, 1e-6f) : 1.f;
        float t_lo = (under < 0.f) ? y / std::max(y - under, 1e-6f) : 1.f;
        float t = std::min(1.f, std::max(0.f, std::min(t_hi, t_lo)));
        rgb[i * 3 + 0] = std::min(1.f, std::max(0.f, y + t * (r - y)));
        rgb[i * 3 + 1] = std::min(1.f, std::max(0.f, y + t * (g - y)));
        rgb[i * 3 + 2] = std::min(1.f, std::max(0.f, y + t * (b - y)));
    }
}

void auto_gains(const std::vector<float>& y, int h, int w, float& short_g, float& long_g) {
    std::vector<float> sample;
    for (int i = 0; i < h; i += 4)
        for (int j = 0; j < w; j += 4) sample.push_back(std::max(y[i * w + j], 0.f));
    if (sample.empty()) {
        short_g = long_g = 1;
        return;
    }
    std::vector<float> sorted = sample;
    std::sort(sorted.begin(), sorted.end());
    float hi = sorted[static_cast<size_t>(std::min(sorted.size() - 1, static_cast<size_t>(sorted.size() * 0.997)))];
    short_g = std::min(64.f, std::max(1.f, 0.92f / std::max(hi, 1e-6f)));
    double logsum = 0;
    for (float v : sample) logsum += std::log(v * short_g + 1e-4);
    float key = static_cast<float>(std::exp(logsum / sample.size()));
    float ratio = std::min(8.f, std::max(1.f, 0.20f / std::max(key, 1e-6f)));
    long_g = short_g * ratio;
}

void exposure_fusion(const std::vector<float>& y, int h, int w, const std::vector<float>& gains, float sigma,
                     std::vector<float>& fused) {
    int levels = std::max(1, static_cast<int>(std::log2(std::min(h, w))) - 4);
    const int n = static_cast<int>(gains.size());
    std::vector<std::vector<float>> renders(n, std::vector<float>(static_cast<size_t>(h) * w));
    std::vector<std::vector<float>> weights(n, std::vector<float>(static_cast<size_t>(h) * w));
    for (int k = 0; k < n; ++k) {
        std::vector<float> lin(static_cast<size_t>(h) * w);
        for (int i = 0; i < h * w; ++i) lin[i] = y[i] * gains[k];
        srgb_encode_n(lin.data(), h * w, renders[k].data());
    }
    std::vector<float> total(static_cast<size_t>(h) * w, 0.f);
    for (int k = 0; k < n; ++k) {
        for (int i = 0; i < h * w; ++i) {
            float d = renders[k][i] - 0.5f;
            weights[k][i] = std::exp(-(d * d) / (2.f * sigma * sigma)) + 1e-6f;
            total[i] += weights[k][i];
        }
    }
    std::vector<Gray> acc(levels);
    bool first = true;
    for (int k = 0; k < n; ++k) {
        Gray W, R;
        W.alloc(h, w);
        R.alloc(h, w);
        for (int i = 0; i < h * w; ++i) {
            W.data[i] = weights[k][i] / total[i];
            R.data[i] = renders[k][i];
        }
        std::vector<Gray> gW(levels), gR(levels), lap(levels);
        gW[0] = W;
        gR[0] = R;
        for (int L = 1; L < levels; ++L) pyr_down(gW[L - 1], gW[L]);
        for (int L = 1; L < levels; ++L) pyr_down(gR[L - 1], gR[L]);
        for (int L = 0; L < levels - 1; ++L) {
            Gray up;
            pyr_up(gR[L + 1], up, gR[L].h, gR[L].w);
            lap[L].alloc(gR[L].h, gR[L].w);
            for (size_t i = 0; i < lap[L].data.size(); ++i) lap[L].data[i] = gR[L].data[i] - up.data[i];
        }
        lap[levels - 1] = gR[levels - 1];
        for (int L = 0; L < levels; ++L) {
            if (first) {
                acc[L].alloc(lap[L].h, lap[L].w);
                std::fill(acc[L].data.begin(), acc[L].data.end(), 0.f);
            }
            for (size_t i = 0; i < acc[L].data.size(); ++i) acc[L].data[i] += gW[L].data[i] * lap[L].data[i];
        }
        first = false;
    }
    Gray img = acc[levels - 1];
    for (int L = levels - 2; L >= 0; --L) {
        Gray up;
        pyr_up(img, up, acc[L].h, acc[L].w);
        img.alloc(acc[L].h, acc[L].w);
        for (size_t i = 0; i < img.data.size(); ++i) img.data[i] = up.data[i] + acc[L].data[i];
    }
    fused.resize(static_cast<size_t>(h) * w);
    for (int i = 0; i < h * w; ++i) fused[i] = std::min(1.f, std::max(0.f, img.data[i]));
}

void guided_filter(const float* guide, const float* src, int h, int w, int radius, float eps, float* out) {
    const int k = 2 * radius + 1;
    const size_t n = static_cast<size_t>(h) * w;
    std::vector<float> mean_i(n), mean_p(n), corr(n), mean_ii(n), ip(n), ii(n);
    for (size_t i = 0; i < n; ++i) {
        ip[i] = guide[i] * src[i];
        ii[i] = guide[i] * guide[i];
    }
    box_blur_impl(guide, h, w, k, mean_i.data());
    box_blur_impl(src, h, w, k, mean_p.data());
    box_blur_impl(ip.data(), h, w, k, corr.data());
    box_blur_impl(ii.data(), h, w, k, mean_ii.data());
    std::vector<float> a(n), b(n);
    for (size_t i = 0; i < n; ++i) {
        float cov = corr[i] - mean_i[i] * mean_p[i];
        float var = mean_ii[i] - mean_i[i] * mean_i[i];
        a[i] = cov / (var + eps);
        b[i] = mean_p[i] - a[i] * mean_i[i];
    }
    std::vector<float> mean_a(n), mean_b(n);
    box_blur_impl(a.data(), h, w, k, mean_a.data());
    box_blur_impl(b.data(), h, w, k, mean_b.data());
    for (size_t i = 0; i < n; ++i) out[i] = mean_a[i] * guide[i] + mean_b[i];
}

void finish_rgb(std::vector<float>& rgb, int h, int w) {
    const int n = h * w;
    std::vector<float> y(n), cb(n), cr(n);
    // BT.601 full-range
    for (int i = 0; i < n; ++i) {
        float r = rgb[i * 3], g = rgb[i * 3 + 1], b = rgb[i * 3 + 2];
        y[i] = 0.299f * r + 0.587f * g + 0.114f * b;
        cb[i] = -0.168736f * r - 0.331264f * g + 0.5f * b;
        cr[i] = 0.5f * r - 0.418688f * g - 0.081312f * b;
    }
    std::vector<float> cb2(n), cr2(n);
    guided_filter(y.data(), cb.data(), h, w, 6, 4e-4f, cb2.data());
    guided_filter(y.data(), cr.data(), h, w, 6, 4e-4f, cr2.data());
    std::vector<float> yb(n);
    gauss_sigma1(y.data(), h, w, yb.data());
    // slightly tighter than σ=0.9; sigma1 is close enough for the port
    const float amount = 0.45f, coring = 0.004f;
    for (int i = 0; i < n; ++i) {
        float detail = y[i] - yb[i];
        float d2 = detail * detail;
        detail *= d2 / (d2 + coring * coring);
        float yy = y[i] + amount * detail;
        float r = yy + 1.402f * cr2[i];
        float g = yy - 0.344136f * cb2[i] - 0.714136f * cr2[i];
        float b = yy + 1.772f * cb2[i];
        rgb[i * 3 + 0] = std::min(1.f, std::max(0.f, r));
        rgb[i * 3 + 1] = std::min(1.f, std::max(0.f, g));
        rgb[i * 3 + 2] = std::min(1.f, std::max(0.f, b));
    }
}

void rotate_rgb(std::vector<float>& rgb, int& h, int& w, int deg) {
    deg = ((deg % 360) + 360) % 360;
    if (deg == 0) return;
    std::vector<float> src = rgb;
    int oh = h, ow = w;
    if (deg == 180) {
        for (int y = 0; y < h; ++y)
            for (int x = 0; x < w; ++x) {
                const float* s = src.data() + ((h - 1 - y) * w + (w - 1 - x)) * 3;
                float* d = rgb.data() + (y * w + x) * 3;
                d[0] = s[0];
                d[1] = s[1];
                d[2] = s[2];
            }
        return;
    }
    rgb.assign(static_cast<size_t>(h) * w * 3, 0.f);
    int nh = w, nw = h;
    std::vector<float> dst(static_cast<size_t>(nh) * nw * 3);
    for (int y = 0; y < oh; ++y) {
        for (int x = 0; x < ow; ++x) {
            int ny, nx;
            if (deg == 90) {
                ny = x;
                nx = oh - 1 - y;
            } else {
                ny = ow - 1 - x;
                nx = y;
            }
            const float* s = src.data() + (y * ow + x) * 3;
            float* d = dst.data() + (ny * nw + nx) * 3;
            d[0] = s[0];
            d[1] = s[1];
            d[2] = s[2];
        }
    }
    rgb.swap(dst);
    h = nh;
    w = nw;
}

std::string json_escape(const std::string& s) {
    std::string o;
    o.reserve(s.size());
    for (char c : s) {
        if (c == '"') o += "\\\"";
        else if (c == '\\') o += "\\\\";
        else o += c;
    }
    return o;
}

}  // namespace

void to_planes(const uint16_t* mosaic, int w, int h, int stride, const char* cfa, const float black[4],
               float white, std::vector<float>& planes, int& ph, int& pw) {
    Offs o{};
    if (!parse_cfa(cfa, o)) throw std::runtime_error("unsupported CFA");
    int ew = w - (w & 1), eh = h - (h & 1);
    ph = eh / 2;
    pw = ew / 2;
    planes.resize(static_cast<size_t>(ph) * pw * 4);
    float scale[4];
    for (int c = 0; c < 4; ++c) scale[c] = 1.f / std::max(1.f, white - black[c]);
    for (int y = 0; y < ph; ++y) {
        for (int x = 0; x < pw; ++x) {
            float* d = planes.data() + (static_cast<size_t>(y) * pw + x) * 4;
            for (int c = 0; c < 4; ++c) {
                int iy = y * 2 + o.r[c];
                int ix = x * 2 + o.c[c];
                float v = static_cast<float>(mosaic[iy * stride + ix]);
                d[c] = (v - black[c]) * scale[c];
            }
        }
    }
}

void demosaic_mhc(const float* cfa, int h, int w, const char* pattern, std::vector<float>& rgb) {
    Offs o{};
    if (!parse_cfa(pattern, o)) throw std::runtime_error("unsupported CFA");
    const float G_AT_RB[25] = {0, 0, -1, 0, 0, 0, 0, 2, 0, 0, -1, 2, 4, 2, -1, 0, 0, 2, 0, 0, 0, 0, -1, 0, 0};
    const float ROW[25] = {0, 0, 0.5f, 0, 0, 0, -1, 0, -1, 0, -1, 4, 5, 4, -1, 0, -1, 0, -1, 0, 0, 0, 0.5f, 0, 0};
    const float COL[25] = {0, 0, -1, 0, 0, 0, -1, 4, -1, 0, 0.5f, 0, 5, 0, 0.5f, 0, -1, 4, -1, 0, 0, 0, -1, 0, 0};
    const float DIAG[25] = {0, 0, -1.5f, 0, 0, 0, 2, 0, 2, 0, -1.5f, 0, 6, 0, -1.5f, 0, 2, 0, 2, 0, 0, 0, -1.5f, 0, 0};
    auto scale = [](float* k, const float* src) {
        for (int i = 0; i < 25; ++i) k[i] = src[i] / 8.f;
    };
    float kG[25], kR[25], kC[25], kD[25];
    scale(kG, G_AT_RB);
    scale(kR, ROW);
    scale(kC, COL);
    scale(kD, DIAG);
    std::vector<float> g_rb(static_cast<size_t>(h) * w), row(static_cast<size_t>(h) * w), col(static_cast<size_t>(h) * w),
        diag(static_cast<size_t>(h) * w);
    conv2d(cfa, h, w, kG, 5, g_rb.data());
    conv2d(cfa, h, w, kR, 5, row.data());
    conv2d(cfa, h, w, kC, 5, col.data());
    conv2d(cfa, h, w, kD, 5, diag.data());
    rgb.resize(static_cast<size_t>(h) * w * 3);
    auto is_site = [&](int y, int x, int plane) { return ((y & 1) == o.r[plane]) && ((x & 1) == o.c[plane]); };
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            int i = y * w + x;
            float v = cfa[i];
            bool r = is_site(y, x, 0), gr = is_site(y, x, 1), gb = is_site(y, x, 2), b = is_site(y, x, 3);
            float R = r ? v : (gr ? row[i] : (gb ? col[i] : diag[i]));
            float G = (gr || gb) ? v : g_rb[i];
            float B = b ? v : (gb ? row[i] : (gr ? col[i] : diag[i]));
            rgb[i * 3 + 0] = R;
            rgb[i * 3 + 1] = G;
            rgb[i * 3 + 2] = B;
        }
    }
}

void srgb_encode(const float* linear, int n, float* display) { srgb_encode_n(linear, n, display); }

int select_reference(const std::vector<float>& planes, int n, int ph, int pw) {
    int k = std::min(3, n);
    float best = -1;
    int idx = 0;
    for (int z = 0; z < k; ++z) {
        Plane4 p;
        p.h = ph;
        p.w = pw;
        p.data.assign(planes.begin() + static_cast<size_t>(z) * ph * pw * 4,
                      planes.begin() + static_cast<size_t>(z + 1) * ph * pw * 4);
        float s = frame_sharpness(p);
        if (s > best) {
            best = s;
            idx = z;
        }
    }
    return idx;
}

void box_blur(const float* in, int h, int w, int k, float* out) { box_blur_impl(in, h, w, k, out); }

BurstResult process_burst(const BurstSpec& spec) {
    if (spec.n_frames <= 0 || !spec.mosaics) throw std::runtime_error("empty burst");
    if (spec.width < 2 || spec.height < 2) throw std::runtime_error("mosaic too small");
    Offs offs{};
    if (!parse_cfa(spec.cfa, offs)) throw std::runtime_error("unsupported CFA");
    Timer timer;
    std::vector<std::string> notes;
    int ph = 0, pw = 0;
    std::vector<Plane4> frames;
    {
        auto _ = timer.scope("prepare");
        const int stride = spec.stride_pixels > 0 ? spec.stride_pixels : spec.width;
        for (int z = 0; z < spec.n_frames; ++z) {
            if (!spec.mosaics[z]) throw std::runtime_error("null mosaic pointer");
            std::vector<float> pl;
            int h, w;
            to_planes(spec.mosaics[z], spec.width, spec.height, stride, spec.cfa, spec.black, spec.white, pl, h, w);
            if (z == 0) {
                ph = h;
                pw = w;
            } else if (h != ph || w != pw) {
                throw std::runtime_error("frame size mismatch");
            }
            Plane4 p;
            p.h = h;
            p.w = w;
            p.data = std::move(pl);
            frames.push_back(std::move(p));
        }
        const long mosaic_px = static_cast<long>(spec.width) * spec.height;
        if (spec.max_mosaic_pixels > 0 && mosaic_px > spec.max_mosaic_pixels) {
            notes.push_back("2x plane downsample (on-device pixel budget)");
            for (auto& f : frames) {
                Plane4 d;
                downsample2(f, d);
                f = std::move(d);
            }
            ph = frames[0].h;
            pw = frames[0].w;
        }
    }

    int ref = select_reference([&] {
        std::vector<float> all;
        all.reserve(frames.size() * static_cast<size_t>(ph) * pw * 4);
        for (auto& f : frames) all.insert(all.end(), f.data.begin(), f.data.end());
        return all;
    }(), static_cast<int>(frames.size()), ph, pw);

    if (spec.max_frames > 0 && static_cast<int>(frames.size()) > spec.max_frames) {
        std::vector<int> keep;
        keep.push_back(ref);
        for (int i = 0; i < static_cast<int>(frames.size()) && static_cast<int>(keep.size()) < spec.max_frames; ++i) {
            if (i != ref) keep.push_back(i);
        }
        std::sort(keep.begin(), keep.end());
        std::vector<Plane4> kept;
        int new_ref = 0;
        for (int i = 0; i < static_cast<int>(keep.size()); ++i) {
            if (keep[i] == ref) new_ref = i;
            kept.push_back(std::move(frames[keep[i]]));
        }
        notes.push_back("max_frames=" + std::to_string(spec.max_frames) + " dropped extras");
        frames.swap(kept);
        ref = new_ref;
    }

    float shot[4], readn[4];
    if (spec.have_noise) {
        for (int c = 0; c < 4; ++c) {
            shot[c] = spec.shot[c];
            readn[c] = spec.read[c];
        }
    } else {
        estimate_noise(frames, shot, readn);
        notes.push_back("noise model estimated on device");
    }
    float shot_mean = 0.25f * (shot[0] + shot[1] + shot[2] + shot[3]);
    float read_mean = 0.25f * (readn[0] + readn[1] + readn[2] + readn[3]);

    Plane4 merged;
    std::vector<float> n_eff(static_cast<size_t>(ph) * pw, 1.f);
    std::vector<float> align_disp;
    {
        auto _ = timer.scope("align_fuse");
        const int n = static_cast<int>(frames.size());
        std::vector<float> sharp(n);
        float smax = 0;
        for (int z = 0; z < n; ++z) {
            sharp[z] = frame_sharpness(frames[z]);
            smax = std::max(smax, sharp[z]);
        }
        if (smax <= 0) smax = 1;
        for (int z = 0; z < n; ++z) sharp[z] /= smax;

        Plane4 acc;
        acc.alloc(ph, pw);
        std::vector<float> wsum(static_cast<size_t>(ph) * pw, 0.f);
        std::vector<float> w2sum(static_cast<size_t>(ph) * pw, 0.f);
        Gray gref;
        planes_to_gray(frames[ref], gref);

        for (int z = 0; z < n; ++z) {
            Plane4 use = frames[z];
            std::vector<uint8_t> valid(static_cast<size_t>(ph) * pw, 1);
            if (z != ref && n > 1) {
                Gray galt;
                planes_to_gray(frames[z], galt);
                std::vector<float> flow;
                float md = 0;
                align_tiles(gref, galt, shot_mean, read_mean, true, flow, md);
                align_disp.push_back(md);
                Plane4 warped;
                warp_cubic(frames[z], flow, warped, valid);
                use = std::move(warped);
            }
            std::vector<float> weight(static_cast<size_t>(ph) * pw, 1.f);
            if (z != ref) {
                std::vector<float> d2;
                normalized_residual(frames[ref], use, shot, readn, 5, d2);
                float srel = std::min(1.f, sharp[z] / std::max(sharp[ref], 1e-6f));
                for (int i = 0; i < ph * pw; ++i) {
                    float excess = std::max(d2[i] - 1.f - 0.5f, 0.f);
                    float c = std::exp(-excess / 0.75f);
                    float peak = use.data[i * 4];
                    for (int ch = 1; ch < 4; ++ch) peak = std::max(peak, use.data[i * 4 + ch]);
                    float sat = std::min(1.f, std::max(0.f, (0.98f - peak) / 0.06f));
                    weight[i] = c * sat * srel * (valid[i] ? 1.f : 0.f);
                }
            }
            for (int i = 0; i < ph * pw; ++i) {
                float w = weight[i];
                wsum[i] += w;
                w2sum[i] += w * w;
                float* a = acc.pix(i / pw, i % pw);
                const float* u = use.pix(i / pw, i % pw);
                for (int c = 0; c < 4; ++c) a[c] += w * u[c];
            }
        }
        merged.alloc(ph, pw);
        for (int i = 0; i < ph * pw; ++i) {
            float den = std::max(wsum[i], 1e-12f);
            float* m = merged.pix(i / pw, i % pw);
            const float* a = acc.pix(i / pw, i % pw);
            for (int c = 0; c < 4; ++c) m[c] = a[c] / den;
            n_eff[i] = (den * den) / std::max(w2sum[i], 1e-12f);
        }
    }

    Plane4 denoised;
    {
        auto _ = timer.scope("denoise");
        std::vector<float> var(static_cast<size_t>(ph) * pw * 4);
        for (int i = 0; i < ph * pw; ++i) {
            float ne = std::max(n_eff[i], 1.f);
            for (int c = 0; c < 4; ++c) {
                float x = std::max(merged.data[i * 4 + c], 0.f);
                var[i * 4 + c] = (shot[c] * x + readn[c]) / ne;
            }
        }
        spatial_wiener(merged, var, 1.f, denoised);
    }

    std::vector<float> display;
    int oh = 0, ow = 0;
    float short_g = 1, long_g = 1;
    {
        auto _ = timer.scope("render");
        Plane4 gained;
        gained.alloc(ph, pw);
        float wb[4] = {spec.wb[0], spec.wb[1], spec.wb[1] > 0 ? spec.wb[1] : spec.wb[1], spec.wb[2]};
        // BurstSpec.wb is R, Gr, Gb, B
        wb[0] = spec.wb[0];
        wb[1] = spec.wb[1];
        wb[2] = spec.wb[2];
        wb[3] = spec.wb[3];
        float gmin = wb[0];
        for (int c = 1; c < 4; ++c) gmin = std::min(gmin, wb[c]);
        for (int i = 0; i < ph * pw; ++i) {
            float clip = 1e30f;
            for (int c = 0; c < 4; ++c) clip = std::min(clip, wb[c]);  // min gain → neutral highlights
            for (int c = 0; c < 4; ++c) {
                float v = denoised.data[i * 4 + c] * wb[c];
                gained.data[i * 4 + c] = std::min(v, clip);
            }
        }
        std::vector<float> cfa;
        int ch, cw;
        from_planes(gained, offs, cfa, ch, cw);
        std::vector<float> rgb;
        demosaic_mhc(cfa.data(), ch, cw, spec.cfa, rgb);
        std::vector<float> linear;
        apply_matrix(rgb, ch * cw, spec.ccm, linear);
        for (float& v : linear) v = std::max(v, 0.f);
        std::vector<float> y(static_cast<size_t>(ch) * cw);
        for (int i = 0; i < ch * cw; ++i) y[i] = luminance_pix(linear[i * 3], linear[i * 3 + 1], linear[i * 3 + 2]);
        auto_gains(y, ch, cw, short_g, long_g);
        std::vector<float> gains_y(static_cast<size_t>(ch) * cw, short_g);
        if (long_g / short_g >= 1.05f) {
            std::vector<float> gs;
            const int ne = 3;
            for (int k = 0; k < ne; ++k) {
                float t = k / static_cast<float>(ne - 1);
                gs.push_back(short_g * std::pow(long_g / short_g, t));
            }
            std::vector<float> fused;
            exposure_fusion(y, ch, cw, gs, 0.2f, fused);
            std::vector<float> fused_lin(static_cast<size_t>(ch) * cw);
            srgb_decode_n(fused.data(), ch * cw, fused_lin.data());
            for (int i = 0; i < ch * cw; ++i) {
                float g = fused_lin[i] / std::max(y[i], 1e-6f);
                gains_y[i] = std::min(g, long_g);
            }
        }
        display.resize(static_cast<size_t>(ch) * cw * 3);
        const float black_pt = 0.0015f;
        const float sat = 1.08f;
        for (int i = 0; i < ch * cw; ++i) {
            float g = gains_y[i];
            float r = linear[i * 3] * g;
            float gg = linear[i * 3 + 1] * g;
            float b = linear[i * 3 + 2] * g;
            r = std::max(r - black_pt, 0.f) / (1.f - black_pt);
            gg = std::max(gg - black_pt, 0.f) / (1.f - black_pt);
            b = std::max(b - black_pt, 0.f) / (1.f - black_pt);
            float yy = luminance_pix(r, gg, b);
            r = yy + sat * (r - yy);
            gg = yy + sat * (gg - yy);
            b = yy + sat * (b - yy);
            display[i * 3 + 0] = r;
            display[i * 3 + 1] = gg;
            display[i * 3 + 2] = b;
        }
        compress_gamut(display, ch * cw);
        std::vector<float> enc(display.size());
        srgb_encode_n(display.data(), static_cast<int>(display.size()), enc.data());
        const float contrast = 0.18f;
        for (size_t i = 0; i < enc.size(); ++i) {
            float v = enc[i];
            display[i] = (1 - contrast) * v + contrast * v * v * (3 - 2 * v);
        }
        finish_rgb(display, ch, cw);
        oh = ch;
        ow = cw;
        rotate_rgb(display, oh, ow, spec.orientation_deg);
    }

    BurstResult out;
    out.width = ow;
    out.height = oh;
    out.rgb.resize(static_cast<size_t>(ow) * oh * 3);
    for (size_t i = 0; i < out.rgb.size(); ++i) {
        float v = std::min(1.f, std::max(0.f, display[i]));
        out.rgb[i] = static_cast<uint8_t>(v * 255.f + 0.5f);
    }
    double mean_ne = 0;
    for (float v : n_eff) mean_ne += v;
    mean_ne /= std::max<size_t>(1, n_eff.size());
    std::ostringstream js;
    js << "{";
    js << "\"preset\":\"hie_v0.1\",";
    js << "\"reproduction\":\"hdrplus_tiles + confidence fusion + N_eff spatial Wiener + MHC + local tone + finish\",";
    js << "\"not\":\"hypothesis H1\",";
    js << "\"frames_used\":" << frames.size() << ",";
    js << "\"reference_index\":" << ref << ",";
    js << "\"plane_size\":[" << ph << "," << pw << "],";
    js << "\"output_size\":[" << ow << "," << oh << "],";
    js << "\"mean_n_eff\":" << mean_ne << ",";
    js << "\"short_gain\":" << short_g << ",";
    js << "\"long_gain\":" << long_g << ",";
    js << "\"cfa\":\"" << json_escape(spec.cfa ? spec.cfa : "") << "\",";
    js << "\"timings\":{";
    for (size_t i = 0; i < timer.items.size(); ++i) {
        if (i) js << ",";
        js << "\"" << timer.items[i].first << "\":" << timer.items[i].second;
    }
    js << ",\"total\":" << timer.total << "},";
    js << "\"alignment_mean_disp\":[";
    for (size_t i = 0; i < align_disp.size(); ++i) {
        if (i) js << ",";
        js << align_disp[i];
    }
    js << "],";
    js << "\"notes\":[";
    for (size_t i = 0; i < notes.size(); ++i) {
        if (i) js << ",";
        js << "\"" << json_escape(notes[i]) << "\"";
    }
    js << "]}";
    out.json = js.str();
    return out;
}

}  // namespace hie
