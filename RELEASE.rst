RELEASE_TYPE: minor

When a deployment occurs, ECS services will be tagged with the release id at key "deployment:label".

This provides a way to identify the release a service should be trying to enact (and by looking up that relationship identify which image is associated with which task). 
