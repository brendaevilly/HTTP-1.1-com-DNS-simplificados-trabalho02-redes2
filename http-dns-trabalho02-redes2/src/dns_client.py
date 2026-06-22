"""Cliente DNS com timeout e retransmissão na camada de aplicação."""

from __future__ import annotations

import random
import socket
import time
from dataclasses import dataclass

from src.config import DNS_MAX_RETRIES, DNS_TIMEOUT
from src.dns_protocol import pack_query, unpack_response


@dataclass
class DnsLookupResult:
    ip: str
    duration_s: float
    retries: int
    errors: int
    query_id: int


class DnsClient:
    def __init__(
        self,
        dns_host: str,
        dns_port: int,
        timeout: float = DNS_TIMEOUT,
        max_retries: int = DNS_MAX_RETRIES,
    ) -> None:
        self.dns_host = dns_host
        self.dns_port = dns_port
        self.timeout = timeout
        self.max_retries = max_retries
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def resolve(self, domain: str, scenario: str = "local") -> DnsLookupResult:
        """Resolve domínio com timeout adaptado ao cenário de rede."""
        timeouts = {"A": 0.5, "B": 1.0, "C": 2.0, "local": self.timeout}
        effective_timeout = timeouts.get(scenario, self.timeout)
        query_id = random.randint(1, 65535)
        packet = pack_query(query_id, domain)

        retries = 0
        errors = 0
        start = time.perf_counter()

        for attempt in range(self.max_retries):
            self.sock.settimeout(effective_timeout)
            self.sock.sendto(packet, (self.dns_host, self.dns_port))
            try:
                data, _ = self.sock.recvfrom(4096)
                response = unpack_response(data)
                if response.query_id != query_id:
                    errors += 1
                    retries += 1
                    continue
                if not response.found:
                    raise LookupError(f"Domínio não encontrado: {domain}")
                duration = time.perf_counter() - start
                return DnsLookupResult(
                    ip=response.ip,
                    duration_s=duration,
                    retries=retries,
                    errors=errors,
                    query_id=query_id,
                )
            except socket.timeout:
                retries += 1
                errors += 1
                continue
            except ValueError:
                errors += 1
                retries += 1
                continue

        duration = time.perf_counter() - start
        raise TimeoutError(
            f"DNS timeout após {self.max_retries} tentativas "
            f"({duration:.3f}s, retries={retries})"
        )

    def close(self) -> None:
        self.sock.close()
