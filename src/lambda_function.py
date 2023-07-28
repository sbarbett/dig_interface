import json
import dns.name
import dns.inet
import dns.resolver
import random
import re
import time

def is_valid_hostname(hostname):
    try:
        dns.name.from_text(hostname)
        return True
    except dns.exception.SyntaxError:
        return False
        
def only_ip(ippat, rrdata):
    match = re.search(ippat, rrdata)
    if match:
        return match.group()
        
def get_authoritative_ns(domain):
    default = dns.resolver.get_default_resolver()
    query = dns.message.make_query(domain, dns.rdatatype.NS)
    response = dns.query.udp(query, default.nameservers[0])

    rcode = response.rcode()
    if rcode != dns.rcode.NOERROR:
        if rcode == dns.rcode.NXDOMAIN:
            raise Exception('%s does not exist.' % domain)
        else:
            raise Exception('Error %s' % dns.rcode.to_text(rcode))

    rrsets = response.answer
    if len(rrsets) == 0:
        raise Exception('No answer')
    
    return rrsets
    
def execute_nssearch(domain, resolver):
    nsset = get_authoritative_ns(domain)
    nssearch_results = []
    for rrset in nsset:
        for rr in rrset:
            try:
                soa_answer = resolver.resolve(domain, 'SOA')
                nssearch_results.append(str(soa_answer.rrset))
            except Exception as e:
                nssearch_results.append("Query failed: " + str(e))
    return nssearch_results
    
def dns_trace(domain):
    ippat = r'\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}'
    rootns = ('198.41.0.4', '199.9.14.201', '192.33.4.12',
              '199.7.91.13', '192.203.230.10', '192.5.5.241',
              '192.112.36.4', '198.97.190.53', '192.36.148.17',
              '192.58.128.30', '193.0.14.129', '199.7.83.42',
              '202.12.27.33',)

    srootns = random.choice(rootns)

    # we will accept input such as google.com www.google.com. etc
    if not is_valid_hostname(domain):
        print('{} is not a valid domain'.format(domain))
        raise ValueError

    cleaned_domain = domain.split('.')
    if not cleaned_domain[-1].endswith('.'):
        cleaned_domain.extend('.')
    cleaned_domain.reverse()

    if '' in cleaned_domain:
        cleaned_domain.remove('')

    i = 1
    while i < len(cleaned_domain):
        if i == 1:
            cleaned_domain[i] = cleaned_domain[i]+cleaned_domain[i-1]
        else:
            cleaned_domain[i] = cleaned_domain[i]+'.'+cleaned_domain[i-1]
        i += 1

    additional_ns = []
    for domain in cleaned_domain[1:]:
        name_server = srootns
        ndomain = dns.name.from_text(domain)
        request = dns.message.make_query(ndomain, dns.rdatatype.NS)
        if additional_ns:
            name_server = random.choice(additional_ns)
        try:
            response = dns.query.udp(request, name_server, timeout=10)
        except dns.exception.Timeout:
            print('Dns query timed out.')
            raise dns.exception.Timeout

        additional_ns = []
        for item in response.additional:
            if 'IN AAAA' not in item.to_text():
                ip_ns = only_ip(ippat, item.to_text())
                if ip_ns:
                    additional_ns.append(only_ip(ippat, ip_ns))

        if additional_ns:
            LNS = random.choice(additional_ns)

    request = dns.message.make_query(domain, dns.rdatatype.ANY)
    try:
        response = dns.query.udp(request, LNS, timeout=10)
    except dns.exception.Timeout:
        print('Dns query timed out.')
        raise dns.exception.Timeout

    response_records = []
    for rrset in response.answer:
        response_records.append(rrset.to_text())

    return response_records

def lambda_handler(event, context):
    print("Event Info: ", json.dumps(event))
    # Extract query data from the event
    qdata = json.loads(event['body'])
    print("Query Info: ", json.dumps(qdata))
    
    # Map qdata to its own variables and do some validation
    domains = qdata['domains']
    
    if not domains:
        return {
            'statusCode': 400,
            'body': 'You must supply at least one domain or hostname to query.'
        }
    for domain in domains:
        if not is_valid_hostname(domain):
            return {
                'statusCode': 400,
                'body': 'Invalid hostnames found in the domains: ' + domain
            }
    
    rtype = qdata['type']
    options = {
        "trace": qdata.get('trace', False),
        "short": qdata.get('short', False),
        "norec": qdata.get('norec', False),
        "dnssec": qdata.get('dnssec', False),
        "cdflag": qdata.get('cdflag', False),
        "nssearch": qdata.get('nssearch', False),
    }
    
    nameservers = qdata['nameservers']
    for nameserver in nameservers:
        if not is_valid_hostname(nameserver) and not dns.inet.is_address(nameserver):
            return {
                'statusCode': 400,
                'body': 'Invalid nameservers found: ' + nameserver
            }

    response_body = []
    for domain in domains:
        domain_response = {
            "domain": domain,
            "type": rtype,
            "options": options,
            "results": []
        }
        
        for nameserver in nameservers:
            # Use the resolver
            resolver = dns.resolver.Resolver(configure=False)
            if options["norec"]:
                resolver.set_flags(dns.flags.RD)
            if options["dnssec"]:
                resolver.set_flags(dns.flags.AD)
            if options["cdflag"]:
                resolver.set_flags(dns.flags.CD)
            resolver.nameservers = [nameserver]
            
            if options["trace"]:
                try:
                    trace_result = dns_trace(domain)
                    domain_response["results"].append({
                        "nameserver": nameserver,
                        "answer": trace_result
                    })
                except Exception as e:
                    domain_response["results"].append({
                        "nameserver": nameserver,
                        "answer": "Trace failed: " + str(e)
                    })
                continue
                
            try:
                # Start time
                start_time = time.time()
                
                if options["nssearch"]:
                    f_answer = execute_nssearch(domain, resolver)
                else:
                    if rtype == "NONE":
                        answer = resolver.resolve(domain)
                    else:
                        answer = resolver.resolve(domain, rtype)
                        
                    if options["short"]:
                        # Extract only the data from the response
                        f_answer = [str(record) for record in answer.rrset]
                    else:
                        # Use the full response
                        f_answer = str(answer.rrset)
                        
                # Calculate query time
                query_time = time.time() - start_time
                    
                domain_response["results"].append({
                    "nameserver": nameserver,
                    "answer": f_answer,
                    "msg_size": len(answer.response.to_wire()),
                    "query_id": answer.response.id,
                    "query_time": round(query_time * 1000) # Convert to ms
                })
            except dns.resolver.NoAnswer:
                domain_response["results"].append({
                    "nameserver": nameserver,
                    "answer": "No answer"
                })
            except dns.resolver.NXDOMAIN:
                domain_response["results"].append({
                    "nameserver": nameserver,
                    "answer": "Non-Existent Domain"
                })
            except Exception as e:
                domain_response["results"].append({
                    "nameserver": nameserver,
                    "answer": "Query failed: " + str(e)
                })
        response_body.append(domain_response)

    return {
        'statusCode': 200,
        'body': response_body
    }