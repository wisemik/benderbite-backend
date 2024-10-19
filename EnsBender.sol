//SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import {INameWrapper} from "../wrapper/INameWrapper.sol";
import "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";

interface IAddressResolver {
    function setAddr(
        bytes32 node,
        address a
    ) external;
}

contract SuperBaseRegistrar is ERC1155Holder {
    INameWrapper public immutable wrapper;
    IAddressResolver public immutable resolver;

    constructor(address _wrapper, IAddressResolver _resolver) {
        wrapper = INameWrapper(_wrapper);
        resolver = _resolver;
    }

    /// benderbite.eth
    bytes32 private constant PARENT_NODE =
        0xf04cb2d4988ee77d0a90cad161b82c937873f43f207e1a57d7095f6a6cc4e1b5;

    function register(
        string calldata label,
        address owner
    ) public payable {
        wrapper.setSubnodeOwner(
            PARENT_NODE,
            label,
            address(this),
            0,
            0
        );

        // call the resolver
        bytes32 node = _makeNode(label);
        resolver.setAddr(node, owner);

        wrapper.setSubnodeRecord(
            PARENT_NODE,
            label,
            owner,
            address(resolver),
            0,
            0,
            0
        );
    }


    function _makeNode(string calldata label) public pure returns (bytes32) {
        bytes32 labelhash = keccak256(bytes(label));
        return keccak256(abi.encodePacked(PARENT_NODE, labelhash));
    }
}
