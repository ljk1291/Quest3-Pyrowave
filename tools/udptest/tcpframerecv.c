/* TCP frame sink for the section-6 transport check. It is deliberately a delivery
 * receiver, not a video decoder: it ACKs only after the complete synthetic frame has
 * reached this process. The sender's measured ACK turnaround is therefore neither a
 * one-way latency nor a decode/presentation measurement.
 *
 * tcpframerecv <port> <seconds>
 * Frame: "Q3TF", u32 big-endian frame id, u32 big-endian payload bytes.
 * ACK:   "Q3TA", u32 big-endian frame id.
 */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <math.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define HEADER 12
#define ACK 8
#define MAX_FRAME_BYTES (8u << 20)

static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static int read_full(int fd, unsigned char *buf, size_t count, uint64_t until) {
    size_t original = count;
    while (count) {
        if (now_ns() >= until) return -1;
        ssize_t got = recv(fd, buf, count, 0);
        if (got == 0) return count == original ? 0 : -1;
        if (got < 0) { if (errno == EINTR) continue; return -1; }
        buf += got; count -= (size_t)got;
    }
    return 1;
}

static int write_full(int fd, const unsigned char *buf, size_t count, uint64_t until) {
    while (count) {
        if (now_ns() >= until) return -1;
        ssize_t put = send(fd, buf, count, MSG_NOSIGNAL);
        if (put == 0) return -1;
        if (put < 0) { if (errno == EINTR) continue; return -1; }
        buf += put; count -= (size_t)put;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: tcpframerecv <port> <seconds>\n"); return 2; }
    const int port = atoi(argv[1]);
    const double seconds = atof(argv[2]);
    if (port < 1 || port > 65535 || !isfinite(seconds) || seconds < 1 || seconds > 910) return 2;
    int listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listener < 0) { perror("socket"); return 1; }
    int one = 1; setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET; addr.sin_addr.s_addr = htonl(INADDR_ANY); addr.sin_port = htons((uint16_t)port);
    if (bind(listener, (struct sockaddr *)&addr, sizeof addr) != 0 || listen(listener, 1) != 0) { perror("listen"); close(listener); return 1; }
    struct timeval accept_timeout = {5, 0}; setsockopt(listener, SOL_SOCKET, SO_RCVTIMEO, &accept_timeout, sizeof accept_timeout);
    int client = accept(listener, NULL, NULL); close(listener);
    if (client < 0) { perror("accept"); return 1; }
    struct timeval timeout = {1, 0}; setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
    unsigned char *scratch = malloc(64 * 1024);
    if (!scratch) { close(client); return 1; }
    const uint64_t until = now_ns() + (uint64_t)(seconds * 1000000000.0);
    uint64_t frames = 0, payload_bytes = 0, bad = 0, acks = 0;
    int incomplete = 0;
    while (now_ns() < until) {
        unsigned char header[HEADER];
        int state = read_full(client, header, sizeof header, until);
        if (state == 0) break;
        /* A timeout after a partial stream header cannot be safely resynchronized:
         * stop this probe rather than treating payload bytes as a new header. */
        if (state < 0) { incomplete = 1; break; }
        uint32_t id_net, bytes_net;
        memcpy(&id_net, header + 4, 4); memcpy(&bytes_net, header + 8, 4);
        const uint32_t id = ntohl(id_net), bytes = ntohl(bytes_net);
        if (memcmp(header, "Q3TF", 4) != 0 || bytes == 0 || bytes > MAX_FRAME_BYTES) { bad++; incomplete = 1; break; }
        uint32_t remaining = bytes;
        while (remaining) {
            size_t want = remaining < 64 * 1024 ? remaining : 64 * 1024;
            state = read_full(client, scratch, want, until);
            if (state != 1) break;
            remaining -= (uint32_t)want;
        }
        if (state != 1) { incomplete = 1; break; }
        unsigned char ack[ACK] = {'Q','3','T','A'};
        const uint32_t ack_id = htonl(id); memcpy(ack + 4, &ack_id, 4);
        if (write_full(client, ack, sizeof ack, until) != 1) { incomplete = 1; break; }
        frames++; acks++; payload_bytes += bytes;
    }
    if (now_ns() >= until) incomplete = 1;
    printf("{\"frames_received\":%" PRIu64 ",\"payload_bytes\":%" PRIu64 ",\"acks_sent\":%" PRIu64 ",\"bad_frames\":%" PRIu64 ",\"incomplete\":%s}\n", frames, payload_bytes, acks, bad, incomplete ? "true" : "false");
    free(scratch); close(client); return 0;
}
