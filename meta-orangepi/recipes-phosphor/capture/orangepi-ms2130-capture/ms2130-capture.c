/*
 * Minimal V4L2 MJPEG grabber for MS2130-style USB HDMI capture devices.
 * The most recent complete JPEG frame is atomically published at --output.
 * No USB HID/keyboard/mouse functionality is involved.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <linux/videodev2.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

struct buffer { void *data; size_t length; };
static volatile sig_atomic_t stop;

static void on_signal(int sig) { (void)sig; stop = 1; }

static int xioctl(int fd, unsigned long request, void *arg) {
    int rc;
    do { rc = ioctl(fd, request, arg); } while (rc < 0 && errno == EINTR);
    return rc;
}

static void usage(const char *name) {
    fprintf(stderr, "Usage: %s [--device PATH] [--output PATH] [--width N] [--height N] [--fps N]\n", name);
}

static int publish_frame(const char *path, const void *data, size_t length) {
    char *tmp = NULL;
    if (asprintf(&tmp, "%s.tmp", path) < 0) return -1;
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd < 0) { free(tmp); return -1; }
    const unsigned char *p = data;
    size_t left = length;
    while (left) {
        ssize_t n = write(fd, p, left);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { close(fd); unlink(tmp); free(tmp); return -1; }
        p += n; left -= (size_t)n;
    }
    if (fsync(fd) < 0 || close(fd) < 0 || rename(tmp, path) < 0) {
        unlink(tmp); free(tmp); return -1;
    }
    free(tmp);
    return 0;
}

static size_t complete_jpeg_length(const void *data, size_t length) {
    const unsigned char *jpeg = data;
    if (length < 4 || jpeg[0] != 0xff || jpeg[1] != 0xd8)
        return 0;

    /* UVC devices may pad a payload after the JPEG EOI marker. */
    for (size_t i = length; i > 1; --i) {
        if (jpeg[i - 2] == 0xff && jpeg[i - 1] == 0xd9)
            return i;
    }
    return 0;
}

static int capture_once(const char *device, const char *output,
                        unsigned width, unsigned height, unsigned fps) {
    int fd = open(device, O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return -1;

    struct v4l2_capability cap;
    memset(&cap, 0, sizeof(cap));
    if (xioctl(fd, VIDIOC_QUERYCAP, &cap) < 0 ||
        !(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE) ||
        !(cap.capabilities & V4L2_CAP_STREAMING)) {
        close(fd); return -1;
    }

    struct v4l2_format fmt;
    memset(&fmt, 0, sizeof(fmt));
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(fd, VIDIOC_G_FMT, &fmt) < 0) {
        close(fd); return -1;
    }

    /* A zero width/height means use the format currently negotiated by UVC. */
    if (width) fmt.fmt.pix.width = width;
    if (height) fmt.fmt.pix.height = height;
    if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_MJPEG || width || height) {
        fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_MJPEG;
        fmt.fmt.pix.field = V4L2_FIELD_ANY;
        if (xioctl(fd, VIDIOC_S_FMT, &fmt) < 0 ||
            fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_MJPEG) {
            fprintf(stderr, "MS2130: device does not provide MJPEG\n");
            close(fd); return -1;
        }
    }
    fprintf(stderr, "MS2130: negotiated %ux%u MJPEG\n",
            fmt.fmt.pix.width, fmt.fmt.pix.height);

    struct v4l2_streamparm parm;
    memset(&parm, 0, sizeof(parm));
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator = 1;
    parm.parm.capture.timeperframe.denominator = fps ? fps : 30;
    (void)xioctl(fd, VIDIOC_S_PARM, &parm);

    struct v4l2_requestbuffers req;
    memset(&req, 0, sizeof(req));
    req.count = 4;
    req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (xioctl(fd, VIDIOC_REQBUFS, &req) < 0 || req.count < 2) {
        close(fd); return -1;
    }
    struct buffer *buffers = calloc(req.count, sizeof(*buffers));
    if (!buffers) { close(fd); return -1; }
    unsigned count = req.count;
    for (unsigned i = 0; i < count; ++i) {
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = req.type; buf.memory = req.memory; buf.index = i;
        if (xioctl(fd, VIDIOC_QUERYBUF, &buf) < 0) goto fail;
        buffers[i].length = buf.length;
        buffers[i].data = mmap(NULL, buf.length, PROT_READ | PROT_WRITE,
                               MAP_SHARED, fd, buf.m.offset);
        if (buffers[i].data == MAP_FAILED) { buffers[i].data = NULL; goto fail; }
        if (xioctl(fd, VIDIOC_QBUF, &buf) < 0) goto fail;
    }

    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(fd, VIDIOC_STREAMON, &type) < 0) goto fail;
    unsigned warmup = fps ? fps : 30;
    while (!stop) {
        fd_set fds; FD_ZERO(&fds); FD_SET(fd, &fds);
        struct timeval tv = { .tv_sec = 2, .tv_usec = 0 };
        int ready = select(fd + 1, &fds, NULL, NULL, &tv);
        if (ready < 0 && errno == EINTR) continue;
        if (ready <= 0) break;
        struct v4l2_buffer buf;
        memset(&buf, 0, sizeof(buf));
        buf.type = type; buf.memory = V4L2_MEMORY_MMAP;
        if (xioctl(fd, VIDIOC_DQBUF, &buf) < 0) {
            if (errno == EAGAIN) continue;
            break;
        }
        if (buf.index < count && buf.bytesused) {
            if (warmup) {
                --warmup;
            } else {
                size_t jpeg_length = complete_jpeg_length(
                    buffers[buf.index].data, buf.bytesused);
                if (jpeg_length)
                    (void)publish_frame(output, buffers[buf.index].data,
                                        jpeg_length);
                else
                    fprintf(stderr, "MS2130: discarded incomplete JPEG frame\n");
            }
        }
        if (xioctl(fd, VIDIOC_QBUF, &buf) < 0) break;
    }
    (void)xioctl(fd, VIDIOC_STREAMOFF, &type);
fail:
    for (unsigned i = 0; i < count; ++i)
        if (buffers[i].data) munmap(buffers[i].data, buffers[i].length);
    free(buffers); close(fd);
    return 0;
}

int main(int argc, char **argv) {
    const char *device = "/dev/video0", *output = "/run/ms2130/latest.mjpg";
    unsigned width = 0, height = 0, fps = 30;
    static const struct option opts[] = {
        {"device", required_argument, NULL, 'd'}, {"output", required_argument, NULL, 'o'},
        {"width", required_argument, NULL, 'w'}, {"height", required_argument, NULL, 'h'},
        {"fps", required_argument, NULL, 'f'}, {0, 0, 0, 0}
    };
    int c;
    while ((c = getopt_long(argc, argv, "d:o:w:h:f:", opts, NULL)) != -1) {
        char *end = NULL; unsigned long v;
        switch (c) {
        case 'd': device = optarg; break; case 'o': output = optarg; break;
        case 'w': v = strtoul(optarg, &end, 10); if (!*optarg || *end || !v) return 2; width = v; break;
        case 'h': v = strtoul(optarg, &end, 10); if (!*optarg || *end || !v) return 2; height = v; break;
        case 'f': v = strtoul(optarg, &end, 10); if (!*optarg || *end || !v) return 2; fps = v; break;
        default: usage(argv[0]); return 2;
        }
    }
    signal(SIGINT, on_signal); signal(SIGTERM, on_signal);
    while (!stop) {
        if (capture_once(device, output, width, height, fps) < 0)
            fprintf(stderr, "MS2130: waiting for %s (%s)\n", device, strerror(errno));
        if (!stop) sleep(2);
    }
    return 0;
}
