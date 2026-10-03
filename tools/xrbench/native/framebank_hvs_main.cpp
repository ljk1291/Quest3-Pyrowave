// Copyright (c) 2026 Quest3-Pyrowave contributors
// SPDX-License-Identifier: MIT
// Included after exact metric functions extracted from pinned upstream psnr.cpp.
#include "framebank_y4m.hpp"

static ImageHandle upload_luma(Device &device, uint32_t width, uint32_t height,
                               const std::vector<uint8_t> &pixels)
{
    auto info = ImageCreateInfo::immutable_2d_image(width, height, VK_FORMAT_R8_UNORM);
    info.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    info.initial_layout = VK_IMAGE_LAYOUT_UNDEFINED;
    auto image = device.create_image(info);
    if (!image) throw std::runtime_error("luma image allocation failed");
    auto cmd = device.request_command_buffer();
    cmd->image_barrier(*image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
                       VK_PIPELINE_STAGE_NONE, VK_ACCESS_NONE,
                       VK_PIPELINE_STAGE_2_COPY_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT);
    memcpy(cmd->update_image(*image), pixels.data(), pixels.size());
    cmd->image_barrier(*image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
                       VK_PIPELINE_STAGE_2_COPY_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT,
                       VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);
    device.submit(cmd);
    return image;
}

int main(int argc, char **argv)
{
    try
    {
        std::string reference_path, distorted_path;
        uint32_t frames = 0;
        double ppd = 0.0;
        bool verify_only = false;
        for (int i = 1; i < argc; i++)
        {
            std::string key = argv[i];
            if (key == "--help")
            {
                fprintf(stdout, "Pinned raw-Y4M HVS scorer: --reference FILE --distorted FILE --frames N --pixels-per-degree P [--verify-inputs-only]\n");
                return EXIT_SUCCESS;
            }
            if (key == "--verify-inputs-only") { verify_only = true; continue; }
            if (++i >= argc) throw std::runtime_error("missing option value");
            if (key == "--reference" && reference_path.empty()) reference_path = argv[i];
            else if (key == "--distorted" && distorted_path.empty()) distorted_path = argv[i];
            else if (key == "--frames" && !frames) frames = Framebank::positive_integer(argv[i]);
            else if (key == "--pixels-per-degree" && !ppd)
            {
                char *end = nullptr;
                ppd = std::strtod(argv[i], &end);
                if (!end || *end || !std::isfinite(ppd) || ppd <= 0) throw std::runtime_error("invalid pixels/degree");
            }
            else throw std::runtime_error("unknown or duplicate option");
        }
        if (reference_path.empty() || distorted_path.empty() || !frames || frames > 90 || !ppd)
            throw std::runtime_error("explicit inputs, 1..90 frames and pixels/degree are required");
        Framebank::RawY4M reference(reference_path), distorted(distorted_path);
        if (!reference.same_format(distorted)) throw std::runtime_error("Y4M geometry, rate, chroma or range mismatch");
        const float factor = float(ppd * 180.0 / (reference.height * muglm::pi<double>()));
        if (!std::isfinite(factor) || factor <= 0) throw std::runtime_error("height factor is not representable");
        std::vector<uint8_t> a, b;
        if (verify_only)
        {
            for (uint32_t n = 0; n < frames; n++) { reference.read_frame(a); distorted.read_frame(b); }
            if (!reference.at_end() || !distorted.at_end()) throw std::runtime_error("extra Y4M frames or bytes");
            fprintf(stdout, "VerifiedFrames = %u; no GPU work or metric result\n", frames);
            return EXIT_SUCCESS;
        }

        Global::init(Global::MANAGER_FEATURE_DEFAULT_BITS, 1);
        // argv[0] is an absolute packaged-tool path supplied by the frame-bank runner.
        Filesystem::setup_default_filesystem(GRANITE_FILESYSTEM(), Path::basedir(argv[0]));
        Context::SystemHandles system = {};
        system.filesystem = GRANITE_FILESYSTEM();
        system.thread_group = GRANITE_THREAD_GROUP();
        if (!Context::init_loader(nullptr)) throw std::runtime_error("Vulkan loader unavailable");
        Context context;
        context.set_system_handles(system);
        context.set_num_thread_indices(GRANITE_THREAD_GROUP()->get_num_threads() + 1);
        if (!context.init_instance_and_device(nullptr, 0, nullptr, 0)) throw std::runtime_error("Vulkan device creation failed");
        Device device;
        device.set_context(context);
        uint64_t total_pixels = 0;
        double total_error = 0.0;
        for (uint32_t n = 0; n < frames; n++)
        {
            reference.read_frame(a); distorted.read_frame(b);
            auto image_a = upload_luma(device, reference.width, reference.height, a);
            auto image_b = upload_luma(device, reference.width, reference.height, b);
            BufferCreateInfo buffer_info = {};
            buffer_info.size = sizeof(uint64_t);
            buffer_info.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT;
            buffer_info.domain = BufferDomain::LinkedDeviceHost;
            buffer_info.misc = BUFFER_MISC_ZERO_INITIALIZE_BIT;
            auto buffer = device.create_buffer(buffer_info);
            if (!buffer) throw std::runtime_error("metric buffer allocation failed");
            auto sync = compute_total_errors_psnr_hvs_m(device, image_a->get_view(), image_b->get_view(),
                                                       *buffer, &factor, 1, total_pixels);
            // The outer owned-process lease also enforces a finite command deadline.
            sync.fence->wait();
            auto *error = static_cast<const uint64_t *>(device.map_host_buffer(*buffer, MEMORY_ACCESS_READ_BIT));
            total_error += ldexp(double(*error), -24);
            device.next_frame_context();
        }
        if (!reference.at_end() || !distorted.at_end()) throw std::runtime_error("extra Y4M frames or bytes");
        // Preserve the pinned upstream peak calculation, including its limited-range convention.
        const double peak = reference.full_range ? 1.0 : (223.0 * 223.0) / (255.0 * 255.0);
        const double result = 10.0 * std::log10(double(total_pixels) * peak / total_error);
        fprintf(stdout, "ScoredFrames = %u || PixelsPerDegree = %.9f || HeightFactor = %.9f || PSNR-HVS-M-H: (Y) %.9f dB\n",
                frames, ppd, double(factor), result);
        return EXIT_SUCCESS;
    }
    catch (const std::exception &error)
    {
        fprintf(stderr, "frame-bank HVS scorer failed: %s\n", error.what());
        return EXIT_FAILURE;
    }
}
